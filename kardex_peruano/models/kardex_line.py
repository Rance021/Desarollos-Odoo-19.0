# -*- coding: utf-8 -*-
from odoo import models, fields


class KardexLine(models.TransientModel):
    _name = 'kardex.peruano.line'
    _description = 'Linea de Kardex Peruano'
    _order = 'fecha_proceso asc, id asc'

    wizard_id = fields.Many2one(
        'kardex.peruano.wizard', ondelete='cascade')
    fecha_proceso = fields.Date(string='Fecha Proceso')
    numero_documento = fields.Char(string='Numero Documento')
    tipo = fields.Selection([
        ('ENTRADA', 'ENTRADA'),
        ('SALIDA', 'SALIDA'),
    ], string='Tipo')
    movimiento = fields.Char(string='Movimiento')
    precio_ingreso = fields.Float(string='Precio Ingreso', digits=(12, 2))
    cantidad = fields.Float(string='Cantidad', digits=(12, 2))
    costo_promedio = fields.Float(string='C.P.', digits=(12, 5))
    costo = fields.Float(string='Costo', digits=(12, 2))
    saldo = fields.Float(string='Saldo', digits=(12, 2))
    valor_stock = fields.Float(string='Valor Stock', digits=(12, 2))
    move_id = fields.Many2one('stock.move', string='Movimiento Stock')
    picking_id = fields.Many2one('stock.picking', string='Transferencia')
