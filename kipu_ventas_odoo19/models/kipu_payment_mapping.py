# -*- coding: utf-8 -*-
from odoo import models, fields

class KipuPaymentMapping(models.Model):
    _name = 'kipu.payment.mapping'
    _description = 'Mapeo de Métodos de Pago Kipu'
    _rec_name = 'nombre_forma_pago'

    nombre_forma_pago = fields.Char(
        string='Nombre en Kipu',
        required=True,
        help="El nombre exacto que devuelve la API de Kipu para esta forma de pago (Ej. 'Efectivo', 'Visa')."
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario de Pago',
        required=True,
        domain=[('type', 'in', ('bank', 'cash'))],
        help="Diario en Odoo con el que se registrarán los pagos de este método."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )

    _sql_constraints = [
        ('unique_nombre_forma_pago', 'unique(nombre_forma_pago, company_id)', 'El nombre del método de pago debe ser único por compañía.')
    ]
