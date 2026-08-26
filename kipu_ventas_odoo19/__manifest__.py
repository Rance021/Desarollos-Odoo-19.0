# -*- coding: utf-8 -*-
{
    'name': 'Kipu - Sincronización',
    'version': '19.0.1.0.0',
    'summary': 'Importa documentos de venta desde la API Kipu/Arándano a Odoo 19',
    'author': 'Mikipu SAC',
    'category': 'Sales/Sales',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'account', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/kipu_config_views.xml',
        'views/kipu_payment_mapping_views.xml',
        'views/account_move_views.xml',
        'views/kipu_venta_views.xml',
        'views/kipu_venta_search.xml',
        'wizard/kipu_sync_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
