# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta


class KipuSyncWizard(models.TransientModel):
    _name = 'kipu.sync.wizard'
    _description = 'Asistente de sincronización Kipu'

    config_id = fields.Many2one(
        'kipu.sync.config',
        string='Configuración Kipu',
        required=True,
        domain=[('active', '=', True)],
    )
    fecha_inicio = fields.Date(
        string='Fecha inicio',
        required=True,
        default=lambda self: date.today() - timedelta(days=7),
    )
    fecha_fin = fields.Date(
        string='Fecha fin',
        required=True,
        default=fields.Date.today,
    )

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_rango(self):
        for rec in self:
            if rec.fecha_inicio > rec.fecha_fin:
                raise UserError(_('La fecha inicio no puede ser mayor a la fecha fin.'))
            delta = (rec.fecha_fin - rec.fecha_inicio).days
            if delta > 61:
                raise UserError(_('El rango máximo permitido por la API Kipu es 2 meses.'))

    def action_sincronizar(self):
        self.ensure_one()
        resultado = self.env['kipu.venta'].sincronizar_desde_api(
            self.config_id,
            self.fecha_inicio,
            self.fecha_fin,
        )
        mensaje = _(
            'Sincronización completada:\n'
            '• Documentos creados: %(creados)s\n'
            '• Documentos actualizados: %(actualizados)s\n'
            '• Omitidos: %(omitidos)s'
        ) % resultado

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Kipu — Sincronización exitosa'),
                'message': mensaje,
                'type': 'success',
                'sticky': True,
            }
        }
