# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    kipu_reference = fields.Char(string='Referencia de Factura Kipu', copy=False, help='Número de comprobante original emitido en Kipu')
