# -*- coding: utf-8 -*-
{
    'name': 'Manufacturing Cost Rationing - MRP Byproduct Cost Share',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Reparto automático de costos en subproductos según cantidad producida',
    'images': ['static/description/main_screenshot.png'],
    'license': 'OPL-1',
    'price': 35.00,
    'currency': 'USD', 
    'author': 'FerGonSolutions',
    'depends': [
        'mrp',
        'mrp_account',
    ],
    'data': [
        'views/mrp_production_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
