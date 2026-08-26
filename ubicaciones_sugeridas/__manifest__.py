{
    'name': 'Ubicaciones Sugeridas en Traslados',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Muestra ubicaciones con stock al seleccionar producto en traslados',
    'author': 'Personalización Odoo',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
