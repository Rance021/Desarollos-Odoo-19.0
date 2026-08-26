from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Cuenta de detracciones para Ventas ──────────────────────────────────
    x_cuenta_detraccion_ventas_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta Detracciones Ventas',
        config_parameter='pe_detracciones.cuenta_ventas_id',
        
        help='Cuenta contable donde se registra la detracción en facturas de cliente '
             '(ej. 104.13 - Cuentas Corrientes en Instituciones Financieras - Detracciones).',
    )

    # ── Cuenta de detracciones para Compras ─────────────────────────────────
    x_cuenta_detraccion_compras_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta Detracciones Compras',
        config_parameter='pe_detracciones.cuenta_compras_id',
        
        help='Cuenta contable donde se registra la detracción en facturas de proveedor.',
    )

    # ── Porcentaje por defecto ───────────────────────────────────────────────
    x_detraccion_porcentaje_defecto = fields.Float(
        string='% Detracción por Defecto',
        digits=(5, 2),
        config_parameter='pe_detracciones.porcentaje_defecto',
        help='Porcentaje de detracción que se pre-carga en las facturas al activar '
             'el checkbox. Se puede editar manualmente en cada factura.',
    )
