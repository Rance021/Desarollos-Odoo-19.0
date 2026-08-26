# -*- coding: utf-8 -*-
"""
Kardex Peruano - Wizard principal
Genera el Kardex valorizado de inventario según normativa SUNAT (Perú)
Método de valuación: Promedio Ponderado

Lógica:
  ENTRADA: nuevo_CP = (valor_stock_ant + costo_ingreso) / (saldo_ant + qty)
  SALIDA:  costo = qty * CP_vigente (negativo), CP no cambia
  Saldo inicial: recorre stock.move anteriores a date_from cronológicamente
"""
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)


class KardexPeruanoWizard(models.TransientModel):
    _name = 'kardex.peruano.wizard'
    _description = 'Kardex Peruano de Inventario'
    _rec_name = 'product_id'

    # ── Filtros ──────────────────────────────────────────────────────────────────
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        domain=[('usage', '=', 'internal')],
        help='Dejar vacío para considerar todas las ubicaciones internas',
    )
    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=lambda self: date.today(),
    )
    include_opening = fields.Boolean(
        string='Incluir Saldo Inicial',
        default=True,
    )

    # ── Resultado ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'kardex.peruano.line',
        'wizard_id',
        string='Líneas del Kardex',
    )
    has_lines = fields.Boolean(compute='_compute_has_lines')

    total_entradas_qty = fields.Float(digits=(12, 2), compute='_compute_totals')
    total_salidas_qty = fields.Float(digits=(12, 2), compute='_compute_totals')
    total_entradas_valor = fields.Float(digits=(12, 2), compute='_compute_totals')
    total_salidas_valor = fields.Float(digits=(12, 2), compute='_compute_totals')
    saldo_final_qty = fields.Float(digits=(12, 2), compute='_compute_totals')
    saldo_final_valor = fields.Float(digits=(12, 2), compute='_compute_totals')

    product_name = fields.Char(compute='_compute_product_info')
    product_code = fields.Char(compute='_compute_product_info')
    product_uom = fields.Char(compute='_compute_product_info')

    @api.depends('line_ids')
    def _compute_has_lines(self):
        for rec in self:
            rec.has_lines = bool(rec.line_ids)

    @api.depends('line_ids.cantidad', 'line_ids.costo', 'line_ids.tipo',
                 'line_ids.saldo', 'line_ids.valor_stock')
    def _compute_totals(self):
        for rec in self:
            entradas = rec.line_ids.filtered(lambda l: l.tipo == 'ENTRADA')
            salidas = rec.line_ids.filtered(lambda l: l.tipo == 'SALIDA')
            rec.total_entradas_qty = sum(entradas.mapped('cantidad'))
            rec.total_salidas_qty = abs(sum(salidas.mapped('cantidad')))
            rec.total_entradas_valor = sum(entradas.mapped('costo'))
            rec.total_salidas_valor = abs(sum(salidas.mapped('costo')))
            if rec.line_ids:
                last = rec.line_ids[-1]
                rec.saldo_final_qty = last.saldo
                rec.saldo_final_valor = last.valor_stock
            else:
                rec.saldo_final_qty = 0.0
                rec.saldo_final_valor = 0.0

    @api.depends('product_id')
    def _compute_product_info(self):
        for rec in self:
            if rec.product_id:
                rec.product_name = rec.product_id.display_name
                rec.product_code = rec.product_id.default_code or ''
                rec.product_uom = rec.product_id.uom_id.name or 'UND'
            else:
                rec.product_name = ''
                rec.product_code = ''
                rec.product_uom = ''

    # ── Método principal ─────────────────────────────────────────────────────────
    def action_generar_kardex(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError('Debe seleccionar un producto.')
        if self.date_from > self.date_to:
            raise UserError('La fecha desde no puede ser mayor a la fecha hasta.')

        self.line_ids.unlink()

        product = self.product_id
        location_ids = self._get_location_ids()

        saldo_qty = 0.0
        valor_stock = 0.0
        costo_promedio = 0.0

        if self.include_opening:
            saldo_qty, valor_stock, costo_promedio = self._calcular_saldo_inicial(
                product, location_ids
            )

        lines_to_create = []

        if self.include_opening and saldo_qty:
            lines_to_create.append({
                'wizard_id': self.id,
                'fecha_proceso': self.date_from,
                'numero_documento': '',
                'tipo': 'ENTRADA',
                'movimiento': 'Inventario Inicial',
                'precio_ingreso': 0.0,
                'cantidad': saldo_qty,
                'costo_promedio': costo_promedio,
                'costo': valor_stock,
                'saldo': saldo_qty,
                'valor_stock': valor_stock,
            })

        moves = self._get_stock_moves(product, location_ids)

        for move in moves:
            move_date = move.date.date() if hasattr(move.date, 'date') else move.date
            es_entrada = move.location_dest_id.id in location_ids
            cantidad = move.product_uom_qty
            precio_unit = self._get_costo_unitario(move)
            costo_total = precio_unit * cantidad
            numero_doc = self._get_numero_documento(move)
            tipo_mov = self._get_tipo_movimiento(move)

            if es_entrada:
                nuevo_valor = valor_stock + costo_total
                nuevo_saldo = saldo_qty + cantidad
                costo_promedio = nuevo_valor / nuevo_saldo if nuevo_saldo else precio_unit
                saldo_qty = nuevo_saldo
                valor_stock = nuevo_valor
                costo_line = costo_total
            else:
                costo_line = -(cantidad * costo_promedio)
                saldo_qty = saldo_qty - cantidad
                valor_stock = saldo_qty * costo_promedio

            lines_to_create.append({
                'wizard_id': self.id,
                'fecha_proceso': move_date,
                'numero_documento': numero_doc,
                'tipo': 'ENTRADA' if es_entrada else 'SALIDA',
                'movimiento': tipo_mov,
                'precio_ingreso': precio_unit if es_entrada else 0.0,
                'cantidad': cantidad if es_entrada else -cantidad,
                'costo_promedio': costo_promedio,
                'costo': costo_line,
                'saldo': saldo_qty,
                'valor_stock': valor_stock,
                'move_id': move.id,
                'picking_id': move.picking_id.id if move.picking_id else False,
            })

        if lines_to_create:
            self.env['kardex.peruano.line'].create(lines_to_create)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kardex.peruano.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _get_location_ids(self):
        if self.location_id:
            return self.location_id.ids
        return self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', 'in', [self.env.company.id, False]),
        ]).ids

    def _calcular_saldo_inicial(self, product, location_ids):
        domain = [
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('date', '<', datetime.combine(self.date_from, datetime.min.time())),
            ('company_id', '=', self.env.company.id),
            '|',
            ('location_id', 'in', location_ids),
            ('location_dest_id', 'in', location_ids),
        ]
        moves = self.env['stock.move'].search(domain, order='date asc, id asc')

        saldo_qty = 0.0
        valor_stock = 0.0
        costo_promedio = 0.0

        for move in moves:
            es_entrada = move.location_dest_id.id in location_ids
            qty = move.product_uom_qty
            precio_unit = self._get_costo_unitario(move)
            costo_total = precio_unit * qty

            if es_entrada:
                nuevo_valor = valor_stock + costo_total
                nuevo_saldo = saldo_qty + qty
                costo_promedio = nuevo_valor / nuevo_saldo if nuevo_saldo else precio_unit
                saldo_qty = nuevo_saldo
                valor_stock = nuevo_valor
            else:
                saldo_qty = saldo_qty - qty
                valor_stock = saldo_qty * costo_promedio

        return saldo_qty, valor_stock, costo_promedio

    def _get_stock_moves(self, product, location_ids):
        domain = [
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('date', '>=', datetime.combine(self.date_from, datetime.min.time())),
            ('date', '<=', datetime.combine(self.date_to, datetime.max.time())),
            ('company_id', '=', self.env.company.id),
            '|',
            ('location_id', 'in', location_ids),
            ('location_dest_id', 'in', location_ids),
        ]
        return self.env['stock.move'].search(domain, order='date asc, id asc')

    def _get_costo_unitario(self, move):
        # 1. Precio de línea de OC
        if move.purchase_line_id:
            po_line = move.purchase_line_id
            price = po_line.price_unit
            if po_line.currency_id != move.company_id.currency_id:
                price = po_line.currency_id._convert(
                    price,
                    move.company_id.currency_id,
                    move.company_id,
                    move.date,
                )
            return price
        # 2. price_unit del move si existe
        if hasattr(move, 'price_unit') and move.price_unit:
            return move.price_unit
        # 3. Costo estándar del producto
        return move.product_id.standard_price or 0.0

    def _get_numero_documento(self, move):
        if move.picking_id:
            if move.picking_id.purchase_id:
                po = move.picking_id.purchase_id
                invoices = po.invoice_ids.filtered(lambda i: i.state == 'posted')
                if invoices:
                    return invoices[0].name
                return po.name
            if move.picking_id.sale_id:
                so = move.picking_id.sale_id
                invoices = so.invoice_ids.filtered(lambda i: i.state == 'posted')
                if invoices:
                    return invoices[0].name
                return so.name
            return move.picking_id.name or ''
        return move.origin or ''

    def _get_tipo_movimiento(self, move):
        if not move.picking_type_id:
            return move.origin or 'Ajuste'
        code = move.picking_type_id.code
        if code == 'incoming':
            return 'Compra'
        elif code == 'outgoing':
            return 'Venta'
        elif code == 'internal':
            return 'Transferencia'
        return move.origin or 'Ajuste Inventario'

    # ── Acciones ─────────────────────────────────────────────────────────────────

    def action_imprimir_kardex(self):
        self.ensure_one()
        return self.env.ref(
            'kardex_peruano.action_report_kardex_peruano'
        ).report_action(self)

    def action_exportar_excel(self):
        self.ensure_one()
        import io
        import base64

        try:
            import xlsxwriter
        except ImportError:
            raise UserError(
                'Se requiere xlsxwriter. Instale con: pip install xlsxwriter'
            )

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Kardex')

        # Formatos
        f_title = wb.add_format({
            'bold': True, 'font_size': 13, 'align': 'center',
            'valign': 'vcenter', 'font_color': '#FFFFFF',
            'bg_color': '#1A5276', 'border': 1,
        })
        f_header = wb.add_format({
            'bold': True, 'font_size': 9, 'align': 'center',
            'valign': 'vcenter', 'font_color': '#FFFFFF',
            'bg_color': '#1A5276', 'border': 1, 'text_wrap': True,
        })
        f_label = wb.add_format({
            'bold': True, 'font_size': 9,
            'bg_color': '#D6EAF8', 'border': 1,
        })
        f_val = wb.add_format({'font_size': 9, 'border': 1})
        f_e2 = wb.add_format({
            'font_size': 9, 'border': 1,
            'bg_color': '#EAFAF1', 'num_format': '#,##0.00',
        })
        f_e5 = wb.add_format({
            'font_size': 9, 'border': 1,
            'bg_color': '#EAFAF1', 'num_format': '#,##0.00000',
        })
        f_et = wb.add_format({'font_size': 9, 'border': 1, 'bg_color': '#EAFAF1'})
        f_s2 = wb.add_format({
            'font_size': 9, 'border': 1,
            'bg_color': '#FDEDEC', 'num_format': '#,##0.00',
        })
        f_s5 = wb.add_format({
            'font_size': 9, 'border': 1,
            'bg_color': '#FDEDEC', 'num_format': '#,##0.00000',
        })
        f_st = wb.add_format({'font_size': 9, 'border': 1, 'bg_color': '#FDEDEC'})
        f_tot_l = wb.add_format({
            'bold': True, 'font_size': 9, 'align': 'right',
            'bg_color': '#1A5276', 'font_color': '#FFFFFF', 'border': 1,
        })
        f_tot_v = wb.add_format({
            'bold': True, 'font_size': 9,
            'bg_color': '#1A5276', 'font_color': '#FFFFFF',
            'border': 1, 'num_format': '#,##0.00',
        })

        # Anchos
        ws.set_column(0, 0, 13)
        ws.set_column(1, 1, 18)
        ws.set_column(2, 2, 9)
        ws.set_column(3, 3, 18)
        ws.set_column(4, 4, 13)
        ws.set_column(5, 5, 10)
        ws.set_column(6, 6, 13)
        ws.set_column(7, 7, 12)
        ws.set_column(8, 8, 10)
        ws.set_column(9, 9, 14)

        row = 0

        # Título
        ws.merge_range(row, 0, row, 9, 'KARDEX VALORIZADO DE INVENTARIO', f_title)
        ws.set_row(row, 20)
        row += 1
        ws.merge_range(
            row, 0, row, 9,
            'Metodo: Costo Promedio Ponderado | Empresa: %s' % self.env.company.name,
            f_header,
        )
        row += 1

        # Info producto
        ws.write(row, 0, 'Producto:', f_label)
        ws.merge_range(row, 1, row, 4, self.product_id.display_name, f_val)
        ws.write(row, 5, 'Codigo:', f_label)
        ws.write(row, 6, self.product_id.default_code or '', f_val)
        ws.write(row, 7, 'U.M.:', f_label)
        ws.write(row, 8, self.product_id.uom_id.name or 'UND', f_val)
        row += 1
        ws.write(row, 0, 'Periodo:', f_label)
        periodo = '%s al %s' % (
            self.date_from.strftime('%d/%m/%Y'),
            self.date_to.strftime('%d/%m/%Y'),
        )
        ws.merge_range(row, 1, row, 9, periodo, f_val)
        row += 2

        # Cabecera tabla
        headers = [
            'Fecha\nProceso', 'Nro.\nDocumento', 'Tipo', 'Movimiento',
            'Precio\nIngreso', 'Cantidad', 'C.P.', 'Costo',
            'Saldo', 'Valor\nStock',
        ]
        ws.set_row(row, 30)
        for col, h in enumerate(headers):
            ws.write(row, col, h, f_header)
        row += 1

        # Líneas
        for line in self.line_ids:
            entrada = line.tipo == 'ENTRADA'
            n2 = f_e2 if entrada else f_s2
            n5 = f_e5 if entrada else f_s5
            nt = f_et if entrada else f_st

            ws.write(row, 0, line.fecha_proceso.strftime('%d/%m/%Y'), nt)
            ws.write(row, 1, line.numero_documento or '', nt)
            ws.write(row, 2, line.tipo, nt)
            ws.write(row, 3, line.movimiento or '', nt)
            ws.write(row, 4, line.precio_ingreso or 0.0, n2)
            ws.write(row, 5, line.cantidad, n2)
            ws.write(row, 6, line.costo_promedio, n5)
            ws.write(row, 7, line.costo, n2)
            ws.write(row, 8, line.saldo, n2)
            ws.write(row, 9, line.valor_stock, n2)
            row += 1

        # Totales
        row += 1
        ws.merge_range(row, 0, row, 4, 'TOTALES', f_tot_l)
        ws.write(row, 5, self.total_entradas_qty, f_tot_v)
        ws.write(row, 6, '', f_tot_l)
        ws.write(row, 7, self.total_entradas_valor - self.total_salidas_valor, f_tot_v)
        ws.write(row, 8, self.saldo_final_qty, f_tot_v)
        ws.write(row, 9, self.saldo_final_valor, f_tot_v)

        wb.close()
        output.seek(0)
        xlsx_data = base64.b64encode(output.read()).decode()

        filename = 'Kardex_%s_%s_%s.xlsx' % (
            (self.product_id.default_code or self.product_id.name or 'producto'),
            self.date_from.strftime('%Y%m'),
            self.date_to.strftime('%Y%m'),
        )

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': xlsx_data,
            'mimetype': (
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'
            ),
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }

    # ── Shell helper ─────────────────────────────────────────────────────────────

    @api.model
    def shell_generar_kardex(self, product_ref, date_from, date_to, location_id=None):
        """
        Uso desde shell de Odoo:
            env['kardex.peruano.wizard'].shell_generar_kardex(
                product_ref='3022',
                date_from='2026-03-01',
                date_to='2026-03-31',
            )
        """
        product = self.env['product.product'].search([
            '|',
            ('default_code', '=', product_ref),
            ('name', 'ilike', product_ref),
        ], limit=1)
        if not product:
            raise UserError('Producto no encontrado: %s' % product_ref)

        vals = {
            'product_id': product.id,
            'date_from': date_from,
            'date_to': date_to,
            'include_opening': True,
        }
        if location_id:
            vals['location_id'] = location_id

        wizard = self.create(vals)
        wizard.action_generar_kardex()
        wizard = self.browse(wizard.id)

        result = []
        for line in wizard.line_ids:
            result.append({
                'fecha': str(line.fecha_proceso),
                'documento': line.numero_documento,
                'tipo': line.tipo,
                'movimiento': line.movimiento,
                'precio_ingreso': line.precio_ingreso,
                'cantidad': line.cantidad,
                'cp': round(line.costo_promedio, 5),
                'costo': line.costo,
                'saldo': line.saldo,
                'valor_stock': line.valor_stock,
            })

        sep = '=' * 100
        print(sep)
        print('KARDEX PERUANO - %s' % product.display_name)
        print('Periodo: %s al %s' % (date_from, date_to))
        print(sep)
        hdr = '%-12s %-18s %-8s %-20s %8s %10s %10s %8s %12s'
        print(hdr % (
            'Fecha', 'Documento', 'Tipo', 'Movimiento',
            'Cant', 'C.P.', 'Costo', 'Saldo', 'Val.Stock',
        ))
        print('-' * 100)
        for r in result:
            print(hdr % (
                r['fecha'], r['documento'] or '', r['tipo'],
                r['movimiento'] or '',
                ('%.2f' % r['cantidad']),
                ('%.5f' % r['cp']),
                ('%.2f' % r['costo']),
                ('%.2f' % r['saldo']),
                ('%.2f' % r['valor_stock']),
            ))
        print(sep)
        return result
