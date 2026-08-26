# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import date, timedelta

_logger = logging.getLogger(__name__)


class KipuVenta(models.Model):
    _name = 'kipu.venta'
    _description = 'Documento de venta Kipu'
    _rec_name = 'serie_numero'
    _order = 'fecha_emision desc, serie_numero desc'

    # ── Identificación ──────────────────────────────────────────────────────
    serie_numero = fields.Char(string='Serie/Número', required=True, index=True)
    tipo_documento = fields.Char(string='Tipo documento', size=5)
    config_id = fields.Many2one(
        'kipu.sync.config', string='Config. Kipu', ondelete='restrict', index=True
    )

    # ── Adquirente ───────────────────────────────────────────────────────────
    tipo_doc_adquirente = fields.Char(string='Tipo doc. cliente', size=5)
    num_doc_adquirente = fields.Char(string='N° doc. cliente')
    razon_social = fields.Char(string='Razón social / Cliente')

    # ── Documento afectado (NC/ND) ───────────────────────────────────────────
    serie_numero_afectado = fields.Char(string='Doc. afectado')
    tipo_doc_afectado = fields.Char(string='Tipo doc. afectado', size=5)
    codigo_motivo = fields.Char(string='Cód. motivo', size=2)
    motivo_documento = fields.Char(string='Motivo', size=20)

    # ── Montos ───────────────────────────────────────────────────────────────
    tipo_moneda = fields.Char(string='Moneda', size=10, default='PEN')
    total_neto = fields.Float(string='Total neto', digits=(18, 5))
    total_igv = fields.Float(string='Total IGV', digits=(18, 5))
    total_venta = fields.Float(string='Total venta', digits=(18, 5))
    recargo = fields.Float(string='Recargo', digits=(18, 5))
    total_otros_tributos = fields.Float(string='Otros tributos', digits=(18, 5))
    tipo_cambio = fields.Float(string='T/C', digits=(18, 5))

    # ── Fechas y canales ─────────────────────────────────────────────────────
    fecha_emision = fields.Datetime(string='Fecha emisión')
    hora_emision = fields.Char(string='Hora emisión', size=8)
    npax = fields.Integer(string='N° pasajeros')
    canal = fields.Char(string='Canal', size=100)

    # ── Estado ───────────────────────────────────────────────────────────────
    estado = fields.Selection([
        ('Aceptado', 'Aceptado'),
        ('Anulado', 'Anulado'),
        ('En Proceso', 'En Proceso'),
    ], string='Estado', index=True)

    # ── Relaciones y Estados Odoo ───────────────────────────────────────────
    detalle_ids = fields.One2many('kipu.venta.detalle', 'venta_id', string='Detalle')
    pago_ids = fields.One2many('kipu.venta.pago', 'venta_id', string='Formas de pago')
    company_id = fields.Many2one('res.company', related='config_id.company_id', store=True)
    move_id = fields.Many2one('account.move', string='Factura Odoo', readonly=True, copy=False)
    picking_id = fields.Many2one('stock.picking', string='Albarán Odoo', readonly=True, copy=False)
    account_payment_ids = fields.Many2many('account.payment', string='Pagos en Odoo', copy=False)

    invoice_state = fields.Selection([
        ('to_invoice', 'Por Facturar'),
        ('invoiced', 'Facturado'),
    ], string='Estado Factura', compute='_compute_states', store=True)
    
    picking_state = fields.Selection([
        ('to_deliver', 'Por Despachar'),
        ('delivered', 'Despachado'),
    ], string='Estado Despacho', compute='_compute_states', store=True)
    
    payment_state = fields.Selection([
        ('to_pay', 'Por Pagar'),
        ('paid', 'Pagado'),
    ], string='Estado Pago', compute='_compute_states', store=True)

    @api.depends('move_id', 'picking_id', 'move_id.payment_state', 'pago_ids')
    def _compute_states(self):
        for rec in self:
            rec.invoice_state = 'invoiced' if rec.move_id else 'to_invoice'
            rec.picking_state = 'delivered' if rec.picking_id else 'to_deliver'
            
            if rec.move_id and getattr(rec.move_id, 'payment_state', '') in ('paid', 'in_payment', 'reversed'):
                rec.payment_state = 'paid'
            elif not rec.pago_ids:
                rec.payment_state = 'paid'
            else:
                rec.payment_state = 'to_pay'

    _sql_constraints = [
        ('unique_serie_numero_config',
         'UNIQUE(serie_numero, config_id)',
         'Ya existe este documento para esta configuración Kipu.'),
    ]

    # ────────────────────────────────────────────────────────────────────────
    # Lógica de sincronización
    # ────────────────────────────────────────────────────────────────────────

    @api.model
    def _parse_datetime(self, valor):
        """Parsea string de fecha/hora de la API a datetime o False."""
        if not valor:
            return False
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                from datetime import datetime
                return datetime.strptime(valor, fmt)
            except (ValueError, TypeError):
                continue
        return False

    @api.model
    def sincronizar_desde_api(self, config, fecha_inicio, fecha_fin):
        """
        Sincroniza documentos de la API Kipu para el rango dado.
        Retorna dict con contadores: creados / actualizados / omitidos.
        """
        consulta = config._call_api(fecha_inicio, fecha_fin)

        cabeceras = consulta.get('documentoCabecera') or consulta.get('DocumentoCabecera', [])
        detalles = consulta.get('documentoDetalles') or consulta.get('DocumentoDetalles', [])
        pagos = consulta.get('formaPagos') or consulta.get('FormaPagos', [])

        def g(d, *keys):
            """Get value trying both PascalCase and camelCase keys."""
            for k in keys:
                v = d.get(k)
                if v is not None:
                    return v
                v = d.get(k[0].lower() + k[1:])
                if v is not None:
                    return v
            return None

        # Indexar detalles y pagos por SerieNumero para acceso rápido
        det_por_doc = {}
        for d in detalles:
            key = (g(d, 'SerieNumero'), g(d, 'TipoDocumento'))
            det_por_doc.setdefault(key, []).append(d)

        pag_por_doc = {}
        for p in pagos:
            key = (g(p, 'SerieNumero'), g(p, 'TipoDocumento'))
            pag_por_doc.setdefault(key, []).append(p)

        creados = actualizados = omitidos = 0

        for cab in cabeceras:
            sn = g(cab, 'SerieNumero')
            td = g(cab, 'TipoDocumento')
            if not sn:
                omitidos += 1
                continue

            existing = self.search([
                ('serie_numero', '=', sn),
                ('config_id', '=', config.id),
            ], limit=1)

            vals_cab = {
                'serie_numero': sn,
                'tipo_documento': td,
                'config_id': config.id,
                'tipo_doc_adquirente': g(cab, 'TipoDocumentoAdquirente'),
                'num_doc_adquirente': g(cab, 'NumeroDocumentoAdquirente'),
                'razon_social': g(cab, 'RazonSocialAdquirente'),
                'serie_numero_afectado': g(cab, 'SerieNumeroAfectado'),
                'tipo_doc_afectado': g(cab, 'TipoDocumentoAfectado'),
                'codigo_motivo': g(cab, 'CodigoMotivo'),
                'motivo_documento': g(cab, 'MotivoDocumento'),
                'tipo_moneda': g(cab, 'TipoMoneda') or 'PEN',
                'total_neto': g(cab, 'TotalNeto') or 0.0,
                'total_igv': g(cab, 'TotalIgv') or 0.0,
                'total_venta': g(cab, 'TotalVenta') or 0.0,
                'recargo': g(cab, 'Recargo') or 0.0,
                'total_otros_tributos': g(cab, 'TotalOtrosTributos') or 0.0,
                'tipo_cambio': g(cab, 'TipoCambio') or 0.0,
                'fecha_emision': self._parse_datetime(g(cab, 'FechaEmision')),
                'hora_emision': g(cab, 'HoraEmision'),
                'npax': g(cab, 'Npax') or 0,
                'canal': g(cab, 'Canal'),
                'estado': g(cab, 'Estado'),
            }

            # Construir líneas de detalle
            vals_det = []
            for d in det_por_doc.get((sn, td), []):
                vals_det.append((0, 0, {
                    'codigo_producto': g(d, 'CodigoProducto'),
                    'codigo_clase': g(d, 'CodigoClase'),
                    'nombre_clase': g(d, 'NombreClase'),
                    'codigo_categoria': g(d, 'CodigoCategoria'),
                    'nombre_categoria': g(d, 'NombreCategoria'),
                    'importe_igv': g(d, 'ImporteIgv') or 0.0,
                    'codigo_razon_exoneracion': g(d, 'CodigoRazonExoneracion'),
                    'cantidad': g(d, 'Cantidad') or 0.0,
                    'descripcion': g(d, 'Descripcion'),
                    'categoria': g(d, 'Categoria'),
                    'importe_descuento': g(d, 'ImporteDescuento') or 0.0,
                    'recargo': g(d, 'Recargo') or 0.0,
                    'total_neto': g(d, 'TotalNeto') or 0.0,
                    'total_venta': g(d, 'Totalventa') or g(d, 'TotalVenta') or 0.0,
                    'descuento_porcentaje': g(d, 'DescuentoPorcentaje') or 0.0,
                    'importe_original': d.get('importeOriginal') or d.get('ImporteOriginal') or 0.0,
                    'titulo_descuento': d.get('tituloDescuento') or d.get('TituloDescuento'),
                }))

            # Construir líneas de pago
            vals_pag = []
            for p in pag_por_doc.get((sn, td), []):
                vals_pag.append((0, 0, {
                    'tipo_moneda': g(p, 'TipoMoneda') or 'PEN',
                    'tipo_cambio': g(p, 'TipoCambio') or 0.0,
                    'forma_pago': g(p, 'FormaPago'),
                    'monto': g(p, 'Monto') or 0.0,
                    'fecha_pago': self._parse_datetime(g(p, 'FechaPago')),
                    'id_forma_pago': g(p, 'IdFormaPago') or 0,
                }))

            if existing:
                # Actualizar cabecera y reemplazar detalles/pagos
                existing.detalle_ids.unlink()
                existing.pago_ids.unlink()
                vals_cab['detalle_ids'] = vals_det
                vals_cab['pago_ids'] = vals_pag
                existing.write(vals_cab)
                actualizados += 1
            else:
                vals_cab['detalle_ids'] = vals_det
                vals_cab['pago_ids'] = vals_pag
                self.create(vals_cab)
                creados += 1

        # Actualizar fecha de última sync en la config
        from datetime import datetime
        config.write({
            'ultima_sync': datetime.now(),
            'estado_conexion': 'ok',
            'nota_error': False,
        })

        _logger.info(
            "Kipu sync LocalId=%s: +%d creados, ~%d actualizados, %d omitidos",
            config.local_id, creados, actualizados, omitidos
        )
        return {'creados': creados, 'actualizados': actualizados, 'omitidos': omitidos}

    @api.model
    def cron_sincronizar_ayer(self):
        """
        Acción programada: sincroniza el día anterior para todas las
        configuraciones activas.
        """
        configs = self.env['kipu.sync.config'].search([('active', '=', True)])
        ayer = date.today() - timedelta(days=1)
        for config in configs:
            try:
                self.sincronizar_desde_api(config, ayer, ayer)
            except Exception as e:
                _logger.error(
                    "Error cron Kipu sync LocalId=%s: %s", config.local_id, e
                )
                config.write({'estado_conexion': 'error', 'nota_error': str(e)})

        # Procesar ventas a Odoo
        ventas_en_proceso = self.search([('estado', '=', 'Aceptado'), '|', ('move_id', '=', False), ('picking_id', '=', False)])
        if ventas_en_proceso:
            ventas_en_proceso.action_procesar_odoo()

    def _get_or_create_partner(self):
        self.ensure_one()
        if not self.num_doc_adquirente:
            partner = self.env['res.partner'].search([('name', '=', self.razon_social or 'Cliente Kipu')], limit=1)
            if not partner:
                partner = self.env['res.partner'].create({'name': self.razon_social or 'Cliente Kipu'})
            return partner

        partner = self.env['res.partner'].search([('vat', '=', self.num_doc_adquirente)], limit=1)
        if not partner:
            vals = {
                'name': self.razon_social or 'Cliente Nuevo',
                'vat': self.num_doc_adquirente,
            }
            doc_num = self.num_doc_adquirente.strip() if self.num_doc_adquirente else ''
            if len(doc_num) == 8 and doc_num.isdigit():
                id_type = self.env['l10n_latam.identification.type'].search([('name', 'ilike', 'DNI')], limit=1)
                if id_type: vals['l10n_latam_identification_type_id'] = id_type.id
            elif len(doc_num) == 11 and doc_num.isdigit() and doc_num.startswith(('1', '2')):
                id_type = self.env['l10n_latam.identification.type'].search([('name', 'ilike', 'RUC')], limit=1)
                if id_type: vals['l10n_latam_identification_type_id'] = id_type.id
            else:
                # Default to IVA/VAT or Carnet de extranjeria if requested
                id_type = self.env['ir.model.data']._xmlid_to_res_id('l10n_latam_base.it_vat')
                if id_type: vals['l10n_latam_identification_type_id'] = id_type
                
            partner = self.env['res.partner'].create(vals)
        return partner

    def _get_or_create_product(self, detalle):
        if not detalle.codigo_producto:
            return False
        product = self.env['product.product'].search([('default_code', '=', detalle.codigo_producto)], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': detalle.descripcion or 'Producto Kipu',
                'default_code': detalle.codigo_producto,
                'type': 'consu',
                'is_storable': True,
            })
        return product

    def _create_stock_picking(self, partner):
        self.ensure_one()
        if not self.config_id.warehouse_id:
            return False
        
        warehouse = self.config_id.warehouse_id
        customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not customer_location:
            return False
            
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '=', warehouse.id)
        ], limit=1)

        if not picking_type:
            return False

        picking = self.env['stock.picking'].create({
            'partner_id': partner.id,
            'picking_type_id': picking_type.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': customer_location.id,
            'origin': self.serie_numero,
        })

        has_lines = False
        for det in self.detalle_ids:
            product = self._get_or_create_product(det)
            if not product or not getattr(product, 'is_storable', product.type == 'product'):
                continue
            self.env['stock.move'].create({
                'product_id': product.id,
                'product_uom_qty': det.cantidad,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': warehouse.lot_stock_id.id,
                'location_dest_id': customer_location.id,
            })
            has_lines = True
        
        if has_lines:
            picking.action_confirm()
            picking.action_assign()
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
            picking.button_validate()
            return picking
        else:
            picking.unlink()
            return False

    def action_create_invoice(self):
        for record in self:
            if record.estado != 'Aceptado' or record.move_id:
                continue

            partner = record._get_or_create_partner()
            journal = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', record.config_id.company_id.id)], limit=1)
            if not journal:
                raise UserError(_("No se encontró un Diario de Ventas para la compañía %s.") % record.config_id.company_id.name)
            
            invoice_vals = {
                'move_type': 'out_refund' if record.tipo_documento in ('07', 'NC') else 'out_invoice',
                'partner_id': partner.id,
                'journal_id': journal.id,
                'kipu_reference': record.serie_numero,
                'ref': f"KIPU: {record.serie_numero}",
                'invoice_date': record.fecha_emision,
                'invoice_line_ids': [],
            }

            tax_incluido = self.env['account.tax'].search([
                ('price_include', '=', True),
                ('type_tax_use', '=', 'sale'),
                ('company_id', '=', record.config_id.company_id.id)
            ], limit=1)

            tax_exonerado = self.env['account.tax'].search([
                ('amount', '=', 0.0),
                ('type_tax_use', '=', 'sale'),
                ('company_id', '=', record.config_id.company_id.id)
            ], limit=1)

            for det in record.detalle_ids:
                product = record._get_or_create_product(det)
                line_vals = {
                    'product_id': product.id if product else False,
                    'name': det.descripcion,
                    'quantity': det.cantidad,
                    'price_unit': (det.total_venta / det.cantidad) if det.cantidad else 0.0,
                }
                
                # Asignar impuesto según si hay IGV o no
                if det.importe_igv > 0 and tax_incluido:
                    line_vals['tax_ids'] = [(6, 0, tax_incluido.ids)]
                elif det.importe_igv == 0 and tax_exonerado:
                    line_vals['tax_ids'] = [(6, 0, tax_exonerado.ids)]
                else:
                    # Si no encuentra impuesto, limpiamos para no arrastrar el excluido del producto
                    line_vals['tax_ids'] = [(5, 0, 0)]
                    
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
            
            move = self.env['account.move'].create(invoice_vals)
            move.action_post()
            record.move_id = move.id

    def action_create_payments(self):
        for record in self:
            if not record.move_id or record.payment_state == 'paid':
                continue

            for pago in record.pago_ids:
                mapping = self.env['kipu.payment.mapping'].search([
                    ('nombre_forma_pago', '=', pago.forma_pago),
                    ('company_id', '=', record.config_id.company_id.id)
                ], limit=1)
                
                if not mapping or not mapping.journal_id:
                    raise UserError(_("No se ha configurado el Mapeo de Pagos para '%s' o falta asignarle un Diario. Por favor, configúrelo en Kipu Ventas -> Configuración -> Mapeo de Pagos.") % pago.forma_pago)
                
                payment_method_line = mapping.journal_id.inbound_payment_method_line_ids[:1]
                payment = self.env['account.payment'].create({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': record.move_id.partner_id.id,
                    'amount': pago.monto,
                    'currency_id': record.move_id.currency_id.id,
                    'journal_id': mapping.journal_id.id,
                    'payment_method_line_id': payment_method_line.id if payment_method_line else False,
                    'memo': f"{record.serie_numero} - {pago.forma_pago}",
                    'date': pago.fecha_pago or record.fecha_emision,
                })
                payment.action_post()
                record.account_payment_ids = [(4, payment.id)]
                    
                # Conciliar usando el método nativo de Odoo para asignar pagos
                payment_lines = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable') and not l.reconciled)
                for pline in payment_lines:
                    try:
                        record.move_id.js_assign_outstanding_line(pline.id)
                    except Exception as e:
                        _logger.warning("No se pudo conciliar el pago %s con la factura %s: %s", payment.id, record.move_id.id, e)

    def action_create_picking(self):
        for record in self:
            if record.estado != 'Aceptado' or record.picking_id:
                continue
            partner = record.move_id.partner_id if record.move_id else record._get_or_create_partner()
            picking = record._create_stock_picking(partner)
            if picking:
                record.picking_id = picking.id

    def action_procesar_odoo(self):
        self.action_create_invoice()
        self.action_create_payments()
        self.action_create_picking()

    def action_view_move(self):
        self.ensure_one()
        if self.move_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.move_id.id,
            }

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            return
        return {
            'name': 'Albarán',
            'view_mode': 'form',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_payments(self):
        self.ensure_one()
        if not self.account_payment_ids:
            return
        return {
            'name': 'Pagos',
            'view_mode': 'list,form',
            'res_model': 'account.payment',
            'domain': [('id', 'in', self.account_payment_ids.ids)],
            'type': 'ir.actions.act_window',
        }

# ─────────────────────────────────────────────────────────────────────────────

class KipuVentaDetalle(models.Model):
    _name = 'kipu.venta.detalle'
    _description = 'Detalle de documento de venta Kipu'
    _order = 'id'

    venta_id = fields.Many2one(
        'kipu.venta', string='Documento', required=True, ondelete='cascade', index=True
    )
    codigo_producto = fields.Char(string='Cód. producto', size=30)
    codigo_clase = fields.Char(string='Cód. clase', size=30)
    nombre_clase = fields.Char(string='Clase')
    codigo_categoria = fields.Char(string='Cód. categoría', size=30)
    nombre_categoria = fields.Char(string='Categoría')
    descripcion = fields.Char(string='Descripción', size=200)
    categoria = fields.Char(string='Categoría (alt.)')
    cantidad = fields.Float(string='Cantidad', digits=(16, 4))
    importe_igv = fields.Float(string='IGV', digits=(18, 5))
    codigo_razon_exoneracion = fields.Char(string='Razón exoneración', size=5)
    importe_descuento = fields.Float(string='Descuento S/', digits=(18, 5))
    titulo_descuento = fields.Char(string='Título descuento')
    descuento_porcentaje = fields.Float(string='Descuento %', digits=(6, 4))
    importe_original = fields.Float(string='Precio original', digits=(18, 5))
    recargo = fields.Float(string='Recargo', digits=(18, 5))
    total_neto = fields.Float(string='Total neto', digits=(18, 5))
    total_venta = fields.Float(string='Total venta', digits=(18, 5))


class KipuVentaPago(models.Model):
    _name = 'kipu.venta.pago'
    _description = 'Forma de pago de documento Kipu'
    _order = 'id'

    venta_id = fields.Many2one(
        'kipu.venta', string='Documento', required=True, ondelete='cascade', index=True
    )
    tipo_moneda = fields.Char(string='Moneda', size=10, default='PEN')
    tipo_cambio = fields.Float(string='T/C', digits=(18, 5))
    forma_pago = fields.Char(string='Forma de pago', size=50)
    monto = fields.Float(string='Monto', digits=(18, 2))
    fecha_pago = fields.Datetime(string='Fecha pago')
    id_forma_pago = fields.Integer(string='ID forma pago')
