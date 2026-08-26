{
    'name': 'PE Detracciones en Facturas',
    'version': '19.0.2.3.0',
    'summary': 'Gestión de detracciones SUNAT en facturas de cliente y proveedor',
    'description': """
        Agrega soporte para detracciones en facturas de cliente y proveedor.
        - Checkbox 'Tiene Detracción' en la factura
        - Porcentaje por defecto configurable en Ajustes de Contabilidad
        - Detección automática de código/% desde los productos (opcional)
        - Cuentas contables separadas para ventas y compras
        - Al confirmar, ajusta el asiento: CxC/CxP ↔ Cuenta Detracciones
        - Redondeo a entero en PEN, sin redondeo en otras monedas
    """,
    'author': 'Mikipu SAC',
    'category': 'Accounting/Localizations',
    'depends': [
        'account',
        'l10n_pe',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
