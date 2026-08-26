from odoo import models, fields, api, exceptions


class SaleOrderNotaVenta(models.Model):
    _inherit = 'sale.order'

    nota_venta_count = fields.Integer(
        string='Notas de Venta',
        compute='_compute_nota_venta_count',
    )

    def _compute_nota_venta_count(self):
        for order in self:
            order.nota_venta_count = self.env['account.move'].search_count([
                ('invoice_origin', '=', order.name),
                ('journal_id.code', '=', 'NV'),
                ('move_type', '=', 'out_invoice'),
            ])

    def action_view_nota_ventas(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Notas de Venta',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('invoice_origin', '=', self.name),
                ('journal_id.code', '=', 'NV'),
                ('move_type', '=', 'out_invoice'),
            ],
            'context': {
                'default_move_type': 'out_invoice',
                'default_is_nota_venta': True,
            },
        }

    def action_create_nota_venta(self):
        self.ensure_one()

        journal = self.env['account.journal'].search([
            ('code', '=', 'NV'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        if not journal:
            raise exceptions.UserError(
                'No se encontro el diario NV. '
                'Verifique que el modulo Nota de Ventas este instalado correctamente.'
            )

        invoice_lines = []
        for line in self.order_line:
            if line.display_type in ('line_section', 'line_note'):
                invoice_lines.append((0, 0, {
                    'display_type': line.display_type,
                    'name': line.name,
                }))
                continue

            account = (
                line.product_id.property_account_income_id
                or line.product_id.categ_id.property_account_income_categ_id
            )

            invoice_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.product_uom_qty,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'account_id': account.id if account else False,
            }))

        nota_venta = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': journal.id,
            'partner_id': self.partner_invoice_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.name,
            'ref': self.client_order_ref or self.name,
            'invoice_line_ids': invoice_lines,
        })

        # Refrescar el contador
        self._compute_nota_venta_count()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Nota de Venta',
            'res_model': 'account.move',
            'res_id': nota_venta.id,
            'view_mode': 'form',
            'context': {
                'default_move_type': 'out_invoice',
                'default_is_nota_venta': True,
            },
        }
