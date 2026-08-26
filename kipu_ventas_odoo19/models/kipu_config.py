# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)

KIPU_API_URL = "https://apixacto.mikipu.com/api/documento/consultaArandano"


class KipuSyncConfig(models.Model):
    _name = 'kipu.sync.config'
    _description = 'Configuración de conexión Kipu/Arándano'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True, default='Configuración Kipu')
    token = fields.Char(
        string='Token de autenticación',
        required=True,
        help='JWT token provisto por Kipu para este local'
    )
    local_id = fields.Integer(
        string='Local ID',
        required=True,
        help='Identificador del local en el sistema Kipu'
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén origen',
        help='Almacén principal desde donde se descontará el stock de las ventas de este local.',
        required=True,
        default=lambda self: self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    ultima_sync = fields.Datetime(string='Última sincronización', readonly=True)
    estado_conexion = fields.Selection([
        ('ok', 'Conectado'),
        ('error', 'Error'),
        ('no_probado', 'No probado'),
    ], string='Estado conexión', default='no_probado', readonly=True)
    nota_error = fields.Text(string='Detalle del error', readonly=True)

    def action_probar_conexion(self):
        self.ensure_one()
        from datetime import date, timedelta
        fecha_fin = date.today()
        fecha_ini = fecha_fin - timedelta(days=3)
        payload = {
            "Token": self.token,
            "LocalId": self.local_id,
            "FechaInicio": fecha_ini.strftime('%Y-%m-%d'),
            "FechaFin": fecha_fin.strftime('%Y-%m-%d'),
        }
        try:
            resp = requests.post(KIPU_API_URL, json=payload, timeout=30)
            data = resp.json()
            status = data.get('status', resp.status_code)
            if status == 200:
                self.write({'estado_conexion': 'ok', 'nota_error': False})
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Conexión exitosa'),
                        'message': _('La API Kipu respondió correctamente.'),
                        'type': 'success',
                    }
                }
            else:
                msg = data.get('message', str(data))
                self.write({'estado_conexion': 'error', 'nota_error': msg})
                raise UserError(_('Error de conexión: %s') % msg)
        except requests.exceptions.RequestException as e:
            self.write({'estado_conexion': 'error', 'nota_error': str(e)})
            raise UserError(_('No se pudo conectar a la API Kipu: %s') % str(e))

    def _call_api(self, fecha_inicio, fecha_fin):
        """
        Llama a la API Kipu y retorna el dict con DocumentoCabecera/Detalles/FormaPagos.
        """
        payload = {
            "Token": self.token,
            "LocalId": self.local_id,
            "FechaInicio": fecha_inicio.strftime('%Y-%m-%d'),
            "FechaFin": fecha_fin.strftime('%Y-%m-%d'),
        }
        _logger.info("Kipu API call: LocalId=%s %s → %s", self.local_id, fecha_inicio, fecha_fin)
        _logger.error("Kipu payload: %s", payload)
        try:
            resp = requests.post(KIPU_API_URL, json=payload, timeout=60)
            _logger.error("Kipu HTTP: %s", resp.status_code)
            _logger.error("Kipu raw: %s", resp.text[:800])
            data = resp.json()
        except Exception as e:
            raise UserError(_('Error de comunicación con Kipu: %s') % str(e))

        _logger.error("Kipu response keys: %s", list(data.keys()) if isinstance(data, dict) else type(data))

        status = data.get('status', resp.status_code)
        if status != 200:
            if status == 400:
                raise UserError(_('Kipu API 400: %s') % data.get('message'))
            elif status == 401:
                raise UserError(_('Kipu API 401: Token o Local sin permiso.'))
            elif status == 403:
                raise UserError(_('Kipu API 403: Token desactivado.'))
            else:
                raise UserError(_('Kipu API error %s: %s') % (status, data.get('message')))

        # --- Detectar estructura de respuesta ---
        # Caso 1: {'status':200, 'consulta': {'DocumentoCabecera': [...], ...}}
        # Caso 2: {'status':200, 'DocumentoCabecera': [...], ...}
        # Caso 3: {'status':200, 'data': {'DocumentoCabecera': [...], ...}}

        if 'consulta' in data and isinstance(data['consulta'], dict):
            consulta = data['consulta']
        elif 'DocumentoCabecera' in data:
            consulta = data
        elif 'data' in data and isinstance(data['data'], dict):
            consulta = data['data']
        else:
            # Loggear la estructura completa para debug
            _logger.error("Kipu estructura desconocida: %s", str(data)[:500])
            raise UserError(
                _('Estructura de respuesta Kipu no reconocida.\nKeys: %s\nPrimeros 400 chars: %s')
                % (list(data.keys()), str(data)[:400])
            )

        _logger.info(
            "Kipu consulta: Cabeceras=%s Detalles=%s Pagos=%s",
            len(consulta.get('DocumentoCabecera', [])),
            len(consulta.get('DocumentoDetalles', [])),
            len(consulta.get('FormaPagos', [])),
        )
        return consulta
