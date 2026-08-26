# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockTemperatureWizard(models.TransientModel):
    """Wizard de registro rápido de temperatura."""
    _name = 'stock.temperature.wizard'
    _description = 'Asistente de Registro de Temperatura'

    origin_type = fields.Selection([
        ('reception', 'Recepción'),
        ('batch', 'Lote de Recepción'),
        ('inventory', 'Inventario'),
        ('manufacturing', 'Fabricación'),
    ], string='Origen', required=True)

    picking_id = fields.Many2one('stock.picking', string='Recepción')
    quant_id = fields.Many2one('stock.quant', string='Inventario (Quant)')
    production_id = fields.Many2one('mrp.production', string='Orden de Fabricación')

    date = fields.Datetime(
        string='Fecha / Hora',
        required=True,
        default=fields.Datetime.now,
    )
    temperature = fields.Float(string='Temperatura', required=True, digits=(6, 2))
    temperature_unit = fields.Selection([
        ('C', '°C'),
        ('F', '°F'),
        ('K', 'K'),
    ], string='Unidad', default='C', required=True)

    product_id = fields.Many2one('product.product', string='Producto')
    lot_id = fields.Many2one(
        'stock.lot', string='Lote',
        domain="[('product_id', '=', product_id)]",
    )
    notes = fields.Text(string='Observaciones')

    # Líneas adicionales
    line_ids = fields.One2many(
        'stock.temperature.wizard.line',
        'wizard_id',
        string='Puntos adicionales de medición',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Tomar unidad predeterminada de la configuración
        unit = self.env['ir.config_parameter'].sudo().get_param(
            'temperature_control_mikipu.default_unit', 'C'
        )
        res['temperature_unit'] = unit
        return res

    def action_save(self):
        """Crear el registro de temperatura y confirmar."""
        self.ensure_one()
        vals = {
            'origin_type': self.origin_type,
            'picking_id': self.picking_id.id,
            'quant_id': self.quant_id.id,
            'production_id': self.production_id.id,
            'date': self.date,
            'temperature': self.temperature,
            'temperature_unit': self.temperature_unit,
            'product_id': self.product_id.id,
            'lot_id': self.lot_id.id,
            'notes': self.notes,
            'state': 'confirmed',
            'line_ids': [(0, 0, {
                'description': l.description,
                'temperature': l.temperature,
                'notes': l.notes,
                'sequence': l.sequence,
            }) for l in self.line_ids],
        }
        # Heredar límites del producto si está definido
        if self.product_id:
            tmpl = self.product_id.product_tmpl_id
            vals['min_temp'] = tmpl.temp_min
            vals['max_temp'] = tmpl.temp_max

        log = self.env['stock.temperature.log'].create(vals)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.temperature.log',
            'res_id': log.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_save_and_new(self):
        """Guardar y abrir un nuevo wizard con el mismo contexto."""
        self.action_save()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar Temperatura'),
            'res_model': 'stock.temperature.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }


class StockTemperatureWizardLine(models.TransientModel):
    _name = 'stock.temperature.wizard.line'
    _description = 'Línea de temperatura en wizard'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('stock.temperature.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    description = fields.Char(string='Punto de medición', required=True)
    temperature = fields.Float(string='Temperatura', digits=(6, 2), required=True)
    notes = fields.Char(string='Nota')
