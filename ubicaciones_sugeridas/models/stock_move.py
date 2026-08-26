from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    x_ubicaciones_sugeridas = fields.Char(
        string='Ubicaciones',
        compute='_compute_ubicaciones_sugeridas',
        store=True,
        readonly=True,
        help='Ubicaciones internas con stock disponible del producto seleccionado.',
    )

    @api.depends('product_id')
    def _compute_ubicaciones_sugeridas(self):
        for move in self:
            if not move.product_id:
                move.x_ubicaciones_sugeridas = False
                continue
            quants = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ])
            if not quants:
                move.x_ubicaciones_sugeridas = False
                continue
            nombres = sorted(set(q.location_id.complete_name for q in quants))
            move.x_ubicaciones_sugeridas = ' - '.join(nombres)
