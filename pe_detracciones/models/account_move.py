from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ── Campos principales de detracción ────────────────────────────────────

    x_tiene_detraccion = fields.Boolean(
        string='Tiene Detracción',
        default=False,
        copy=False,
        help='Marcar si esta factura está sujeta al sistema de detracciones SUNAT.',
    )

    x_detraccion_codigo = fields.Char(
        string='Código Detracción',
        copy=False,
        store=True,
        compute='_compute_detraccion_info',
        readonly=False,
        help='Código de detracción (detectado del producto o ingresado manualmente).',
    )

    x_detraccion_porcentaje = fields.Float(
        string='% Detracción',
        digits=(5, 2),
        copy=False,
        store=True,
        compute='_compute_detraccion_info',
        readonly=False,
        help='Porcentaje de detracción. Se toma del parámetro por defecto pero '
             'puede editarse manualmente antes de confirmar.',
    )

    x_detraccion_monto = fields.Monetary(
        string='Monto Detracción',
        currency_field='currency_id',
        compute='_compute_detraccion_monto',
        store=True,
        copy=False,
        help='Importe a detraer: Total Factura × (% Detracción / 100). '
             'Redondeado a entero en soles.',
    )

    x_detraccion_aplicada = fields.Boolean(
        string='Detracción aplicada al asiento',
        default=False,
        copy=False,
        readonly=True,
        help='Indica si ya se generó el asiento de detracción.',
    )

    x_detraccion_asiento_id = fields.Many2one(
        'account.move',
        string='Asiento de Detracción',
        copy=False,
        readonly=True,
        help='Asiento contable separado generado para la detracción.',
    )

    # ── Compute: carga % por defecto desde configuración ────────────────────

    @api.depends(
        'x_tiene_detraccion',
        'move_type',
        'invoice_line_ids.product_id.l10n_pe_withhold_code',
        'invoice_line_ids.product_id.l10n_pe_withhold_percentage',
    )
    def _compute_detraccion_info(self):
        ICP = self.env['ir.config_parameter'].sudo()
        pct_defecto = float(ICP.get_param('pe_detracciones.porcentaje_defecto', 0.0) or 0.0)

        for move in self:
            if not move.x_tiene_detraccion:
                move.x_detraccion_codigo = False
                move.x_detraccion_porcentaje = 0.0
                continue

            codigo = False
            porcentaje = 0.0
            for line in move.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
            ):
                producto = line.product_id
                if not producto:
                    continue
                withhold_code_raw = getattr(producto, 'l10n_pe_withhold_code', False)
                withhold_pct = getattr(producto, 'l10n_pe_withhold_percentage', 0.0) or 0.0

                if withhold_code_raw and hasattr(withhold_code_raw, '_name'):
                    withhold_code_str = withhold_code_raw.name or str(withhold_code_raw.id)
                elif withhold_code_raw:
                    withhold_code_str = str(withhold_code_raw)
                else:
                    withhold_code_str = False

                if withhold_code_str and withhold_pct > porcentaje:
                    porcentaje = withhold_pct
                    codigo = withhold_code_str

            move.x_detraccion_codigo = codigo

            if move.x_detraccion_porcentaje == 0.0:
                move.x_detraccion_porcentaje = porcentaje or pct_defecto

    # ── Compute: calcula el monto ────────────────────────────────────────────

    @api.depends('amount_total', 'x_tiene_detraccion', 'x_detraccion_porcentaje')
    def _compute_detraccion_monto(self):
        for move in self:
            if move.x_tiene_detraccion and move.x_detraccion_porcentaje:
                move.x_detraccion_monto = move.amount_total * (
                    move.x_detraccion_porcentaje / 100.0
                )
            else:
                move.x_detraccion_monto = 0.0

    # ── Override action_post ─────────────────────────────────────────────────

    def action_post(self):
        res = super().action_post()
        if self.env.context.get('_skip_detraccion'):
            return res
        for move in self.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund',
                                      'in_invoice', 'in_refund')
                      and m.x_tiene_detraccion
                      and not m.x_detraccion_aplicada
        ):
            move._aplicar_detraccion_asiento()
        return res

    def _get_cuenta_detraccion(self):
        """Devuelve la cuenta contable de detracción según el tipo de factura."""
        ICP = self.env['ir.config_parameter'].sudo()
        if self.move_type in ('out_invoice', 'out_refund'):
            param = 'pe_detracciones.cuenta_ventas_id'
            label = 'ventas'
        else:
            param = 'pe_detracciones.cuenta_compras_id'
            label = 'compras'

        cuenta_id = int(ICP.get_param(param, 0) or 0)
        if not cuenta_id:
            raise UserError(
                _('No está configurada la cuenta contable de detracciones para %s.\n'
                  'Vaya a Contabilidad → Configuración → Ajustes → '
                  'sección "Detracciones SUNAT".') % label
            )
        cuenta = self.env['account.account'].browse(cuenta_id)
        if not cuenta.exists():
            raise UserError(
                _('La cuenta de detracciones de %s configurada no existe. '
                  'Verifique los ajustes.') % label
            )
        return cuenta

    def _aplicar_detraccion_asiento(self):
        """Crea un asiento contable SEPARADO para la detracción.

        Ventas:
            Crédito CxC          monto  (cliente debe menos)
            Débito  Cta Ventas   monto  (depósito BN)

        Compras:
            Débito  CxP          monto  (debemos menos al proveedor)
            Crédito Cta Compras  monto  (obligación de depósito BN)
        """
        self.ensure_one()

        monto_raw = self.x_detraccion_monto
        if not monto_raw or monto_raw <= 0:
            _logger.warning(
                'Factura %s: detracción activada pero monto es 0. '
                'Verifique el porcentaje y el total.', self.name,
            )
            return

        # Redondear a entero solo en PEN
        monto = round(monto_raw) if self.currency_id.name == 'PEN' else monto_raw

        cuenta_detraccion = self._get_cuenta_detraccion()

        nombre_linea = _('Detracción SUNAT %s%%  [%s]') % (
            self.x_detraccion_porcentaje,
            self.x_detraccion_codigo or '',
        )
        ref_asiento = _('Detracción SUNAT - %s') % (self.name or '')

        if self.move_type in ('out_invoice', 'out_refund'):
            linea_contraparte = self.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
            )
            if not linea_contraparte:
                raise UserError(
                    _('No se encontró la línea de Cuenta por Cobrar en %s.') % self.name
                )
            cuenta_contraparte = linea_contraparte[0].account_id
            linea_contraparte_vals = {'debit': 0.0, 'credit': monto}
            linea_detraccion_vals  = {'debit': monto, 'credit': 0.0}
        else:
            linea_contraparte = self.line_ids.filtered(
                lambda l: l.account_id.account_type == 'liability_payable'
            )
            if not linea_contraparte:
                raise UserError(
                    _('No se encontró la línea de Cuenta por Pagar en %s.') % self.name
                )
            cuenta_contraparte = linea_contraparte[0].account_id
            linea_contraparte_vals = {'debit': monto, 'credit': 0.0}
            linea_detraccion_vals  = {'debit': 0.0, 'credit': monto}

        # Buscar diario tipo 'general' (misceláneos) que no exija tipo de documento
        journal = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.company_id.id)],
            limit=1,
        )
        if not journal:
            raise UserError(
                _('No se encontró un diario de tipo Misceláneos (general). '
                  'Créelo en Contabilidad → Configuración → Diarios.')
            )

        asiento_vals = {
            'move_type': 'entry',
            'ref': ref_asiento,
            'date': self.invoice_date or fields.Date.today(),
            'journal_id': journal.id,
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
            'line_ids': [
                (0, 0, {
                    'name': nombre_linea,
                    'account_id': cuenta_contraparte.id,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                    'x_es_linea_detraccion': True,
                    **linea_contraparte_vals,
                }),
                (0, 0, {
                    'name': nombre_linea,
                    'account_id': cuenta_detraccion.id,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                    'x_es_linea_detraccion': True,
                    **linea_detraccion_vals,
                }),
            ],
        }

        asiento = self.env['account.move'].with_context(
            _skip_detraccion=True
        ).create(asiento_vals)
        asiento.with_context(_skip_detraccion=True).action_post()

        self.x_detraccion_aplicada = True
        self.x_detraccion_asiento_id = asiento.id

        _logger.info(
            'Asiento de detracción %s creado para %s (%s): %.2f %s (%.2f%% de %.2f)',
            asiento.name, self.name, self.move_type, monto, self.currency_id.name,
            self.x_detraccion_porcentaje, self.amount_total,
        )

    # ── Botón manual ─────────────────────────────────────────────────────────

    def action_aplicar_detraccion_manual(self):
        for move in self:
            if move.state != 'posted':
                raise UserError(_('La factura debe estar confirmada.'))
            if not move.x_tiene_detraccion:
                raise UserError(_('Active primero el checkbox "Tiene Detracción".'))
            if move.x_detraccion_aplicada:
                raise UserError(
                    _('La detracción ya fue aplicada. '
                      'Resetee a borrador para recalcular.')
                )
            move._aplicar_detraccion_asiento()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Detracción aplicada'),
                'message': _('Asiento de detracción generado correctamente.'),
                'type': 'success',
                'sticky': False,
            },
        }

    # ── Abrir asiento de detracción ──────────────────────────────────────────

    def action_ver_asiento_detraccion(self):
        self.ensure_one()
        if not self.x_detraccion_asiento_id:
            raise UserError(_('No hay asiento de detracción generado para esta factura.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.x_detraccion_asiento_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Reset a borrador ─────────────────────────────────────────────────────

    def button_draft(self):
        res = super().button_draft()
        for move in self.filtered('x_detraccion_aplicada'):
            move.x_detraccion_aplicada = False
        return res
