# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockTemperatureLog(models.Model):
    _name = 'stock.temperature.log'
    _description = 'Registro de Temperatura'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'

    # ── Identificación ──────────────────────────────────────────────────────
    name = fields.Char(
        string='Referencia',
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
    )

    origin_type = fields.Selection([
        ('reception', 'Recepción'),
        ('inventory', 'Inventario'),
        ('manufacturing', 'Fabricación'),
    ], string='Origen', required=True, index=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', required=True, tracking=True)

    # ── Fechas ───────────────────────────────────────────────────────────────
    date = fields.Datetime(
        string='Fecha / Hora',
        required=True,
        default=fields.Datetime.now,
    )

    # ── Vínculos a documentos ────────────────────────────────────────────────
    picking_id = fields.Many2one(
        'stock.picking',
        string='Recepción',
        ondelete='cascade',
        index=True,
    )
    quant_id = fields.Many2one(
        'stock.quant',
        string='Registro de Inventario (Quant)',
        ondelete='cascade',
        index=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de Fabricación',
        ondelete='cascade',
        index=True,
    )

    # ── Producto / Lote ───────────────────────────────────────────────────────
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        index=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote / Número de serie',
        domain="[('product_id', '=', product_id)]",
    )

    # ── Lecturas de temperatura ───────────────────────────────────────────────
    temperature = fields.Float(
        string='Temperatura (°C)',
        required=True,
        digits=(6, 2),
    )
    temperature_unit = fields.Selection([
        ('C', '°C'),
        ('F', '°F'),
        ('K', 'K'),
    ], string='Unidad', default='C', required=True)
    temperature_celsius = fields.Float(
        string='Temperatura en °C',
        compute='_compute_temperature_celsius',
        store=True,
        digits=(6, 2),
    )

    # ── Límites configurables por producto ───────────────────────────────────
    min_temp = fields.Float(string='Temp. Mínima (°C)', digits=(6, 2))
    max_temp = fields.Float(string='Temp. Máxima (°C)', digits=(6, 2))

    temp_status = fields.Selection([
        ('ok', 'Dentro del rango'),
        ('low', 'Por debajo del mínimo'),
        ('high', 'Por encima del máximo'),
        ('undefined', 'Sin límites definidos'),
    ], string='Estado de Temperatura', compute='_compute_temp_status', store=True)

    # ── Responsable / Notas ───────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
    )
    notes = fields.Text(string='Observaciones')
    alert_sent = fields.Boolean(string='Alerta enviada', default=False)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    # ── Líneas de detalle (múltiples lecturas por registro) ──────────────────
    line_ids = fields.One2many(
        'stock.temperature.log.line',
        'log_id',
        string='Lecturas adicionales',
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Compute / onchange
    # ═══════════════════════════════════════════════════════════════════════
    @api.depends('temperature', 'temperature_unit')
    def _compute_temperature_celsius(self):
        for rec in self:
            t = rec.temperature
            if rec.temperature_unit == 'F':
                rec.temperature_celsius = (t - 32) * 5 / 9
            elif rec.temperature_unit == 'K':
                rec.temperature_celsius = t - 273.15
            else:
                rec.temperature_celsius = t

    @api.depends('temperature_celsius', 'min_temp', 'max_temp')
    def _compute_temp_status(self):
        for rec in self:
            if not rec.min_temp and not rec.max_temp:
                rec.temp_status = 'undefined'
            elif rec.min_temp and rec.temperature_celsius < rec.min_temp:
                rec.temp_status = 'low'
            elif rec.max_temp and rec.temperature_celsius > rec.max_temp:
                rec.temp_status = 'high'
            else:
                rec.temp_status = 'ok'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            product = self.product_id.product_tmpl_id
            self.min_temp = product.temp_min
            self.max_temp = product.temp_max

    # ═══════════════════════════════════════════════════════════════════════
    # Constraints
    # ═══════════════════════════════════════════════════════════════════════
    @api.constrains('min_temp', 'max_temp')
    def _check_temp_range(self):
        for rec in self:
            if rec.min_temp and rec.max_temp and rec.min_temp >= rec.max_temp:
                raise ValidationError(_('La temperatura mínima debe ser menor a la máxima.'))

    # ═══════════════════════════════════════════════════════════════════════
    # ORM overrides
    # ═══════════════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('stock.temperature.log') or _('Nuevo')
        records = super().create(vals_list)
        records._check_alert()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'temperature' in vals or 'temperature_unit' in vals:
            self._check_alert()
        return res

    # ═══════════════════════════════════════════════════════════════════════
    # Business logic
    # ═══════════════════════════════════════════════════════════════════════
    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'

    def _check_alert(self):
        """Envía actividad/notificación si la temperatura está fuera de rango."""
        for rec in self:
            if rec.temp_status in ('low', 'high') and not rec.alert_sent:
                status_label = _('por debajo del mínimo') if rec.temp_status == 'low' else _('por encima del máximo')
                msg = _(
                    'ALERTA: La temperatura %(temp).2f°C está %(status)s '
                    'para el registro %(name)s.',
                    temp=rec.temperature_celsius,
                    status=status_label,
                    name=rec.name,
                )
                rec.activity_schedule(
                    'mail.mail_activity_data_warning',
                    summary=_('Temperatura fuera de rango'),
                    note=msg,
                    user_id=rec.user_id.id or self.env.uid,
                )
                rec.alert_sent = True

    # ═══════════════════════════════════════════════════════════════════════
    # Reporting helpers
    # ═══════════════════════════════════════════════════════════════════════
    def action_print_report(self):
        return self.env.ref(
            'temperature_control_mikipu.action_report_temperature_log'
        ).report_action(self)


class StockTemperatureLogLine(models.Model):
    """Línea de temperatura (para registrar múltiples puntos en un mismo log)."""
    _name = 'stock.temperature.log.line'
    _description = 'Línea de Lectura de Temperatura'
    _order = 'sequence, id'

    log_id = fields.Many2one(
        'stock.temperature.log',
        string='Registro principal',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    description = fields.Char(string='Punto de medición')
    temperature = fields.Float(string='Temperatura', digits=(6, 2), required=True)
    temperature_unit = fields.Selection(
        related='log_id.temperature_unit', readonly=True,
    )
    notes = fields.Char(string='Nota')


# ─── Extensión de product.template para límites de temperatura ────────────────
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    requires_temperature = fields.Boolean(
        string='Requiere control de temperatura',
        help='Activa el registro de temperatura en recepciones, inventarios y fabricación.',
    )
    temp_min = fields.Float(
        string='Temperatura mínima (°C)',
        digits=(6, 2),
        help='Temperatura mínima aceptable en almacén/transporte.',
    )
    temp_max = fields.Float(
        string='Temperatura máxima (°C)',
        digits=(6, 2),
        help='Temperatura máxima aceptable en almacén/transporte.',
    )

    @api.constrains('temp_min', 'temp_max')
    def _check_product_temp_range(self):
        for rec in self:
            if rec.temp_min and rec.temp_max and rec.temp_min >= rec.temp_max:
                raise ValidationError(
                    _('La temperatura mínima del producto debe ser menor a la máxima.')
                )
