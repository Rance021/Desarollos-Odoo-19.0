# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    temperature_mandatory_reception = fields.Boolean(
        string='Temperatura obligatoria en recepciones',
        config_parameter='temperature_control_mikipu.mandatory_reception',
    )
    temperature_mandatory_inventory = fields.Boolean(
        string='Temperatura obligatoria en inventarios',
        config_parameter='temperature_control_mikipu.mandatory_inventory',
    )
    temperature_mandatory_manufacturing = fields.Boolean(
        string='Temperatura obligatoria en fabricación',
        config_parameter='temperature_control_mikipu.mandatory_manufacturing',
    )
    temperature_default_unit = fields.Selection([
        ('C', '°C'),
        ('F', '°F'),
        ('K', 'K'),
    ], string='Unidad de temperatura predeterminada',
       config_parameter='temperature_control_mikipu.default_unit',
       default='C',
    )
