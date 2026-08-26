# -*- coding: utf-8 -*-
# En Odoo 19 el ajuste de inventario físico se hace desde stock.quant
# (acción "Actualizar cantidad"). No existe stock.inventory.
from odoo import models, fields, api, _


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    temperature_log_ids = fields.One2many(
        'stock.temperature.log',
        'quant_id',
        string='Registros de temperatura',
    )
    temperature_log_count = fields.Integer(
        compute='_compute_temperature_log_count',
        string='# Temp. Registradas',
    )

    @api.depends('temperature_log_ids')
    def _compute_temperature_log_count(self):
        for rec in self:
            rec.temperature_log_count = len(rec.temperature_log_ids)

    def action_view_temperature_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'temperature_control_mikipu.action_stock_temperature_log'
        )
        action['domain'] = [('quant_id', '=', self.id)]
        action['context'] = {
            'default_quant_id': self.id,
            'default_origin_type': 'inventory',
            'default_product_id': self.product_id.id,
            'default_lot_id': self.lot_id.id,
        }
        return action

    def action_register_temperature(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar Temperatura del Inventario'),
            'res_model': 'stock.temperature.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_quant_id': self.id,
                'default_origin_type': 'inventory',
                'default_product_id': self.product_id.id,
                'default_lot_id': self.lot_id.id,
            },
        }
