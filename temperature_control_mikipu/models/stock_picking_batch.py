# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class StockPickingBatch(models.Model):

    temperature_log_ids = fields.One2many(
        'stock.temperature.log',
        string='Registros de temperatura del lote',
    )
    temperature_log_count = fields.Integer(
        compute='_compute_temperature_log_count',
        string='# Temp. Registradas',
    )
    temp_status_summary = fields.Selection([
        ('ok', 'Todo en rango'),
        ('warning', 'Fuera de rango'),
        ('pending', 'Pendiente de registro'),
        ('na', 'No aplica'),
    ], string='Estado de Temperatura', compute='_compute_temp_status_summary', store=True)

    @api.depends('temperature_log_ids')
    def _compute_temperature_log_count(self):
        for rec in self:
            rec.temperature_log_count = len(rec.temperature_log_ids)

    @api.depends('temperature_log_ids.temp_status', 'temperature_log_ids.state')
    def _compute_temp_status_summary(self):
        for rec in self:
            logs = rec.temperature_log_ids.filtered(lambda l: l.state == 'confirmed')
            if not logs:
                rec.temp_status_summary = 'pending'
            elif any(l.temp_status in ('low', 'high') for l in logs):
                rec.temp_status_summary = 'warning'
            else:
                rec.temp_status_summary = 'ok'

    def action_view_temperature_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'temperature_control_mikipu.action_stock_temperature_log'
        )
        action['context'] = {
            'default_origin_type': 'batch',
        }
        return action

    def action_register_temperature(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar Temperatura del Lote'),
            'res_model': 'stock.temperature.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_origin_type': 'batch',
            },
        }
