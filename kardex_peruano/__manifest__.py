# -*- coding: utf-8 -*-
{
    'name': 'Kardex Peruano de Inventario',
    'version': '19.0.1.0.0',
    'summary': 'Kardex valorizado de inventario según normativa peruana (SUNAT)',
    'author': 'Personalización Odoo Perú',
    'category': 'Inventory/Reporting',
    'depends': ['stock', 'purchase', 'sale_stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/kardex_wizard_views.xml',
        'views/kardex_menu_views.xml',
        'report/kardex_report_templates.xml',
        'report/kardex_report_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kardex_peruano/static/src/css/kardex.css',
        ],
    },
    'installable': True,
    'license': 'LGPL-3',
}
