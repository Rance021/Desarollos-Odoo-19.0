# -*- coding: utf-8 -*-
{
    'name': 'Temperature Control',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Quality',
    'summary': 'Registro de temperaturas en recepciones, inventarios y fabricación',
    'description': """
        Módulo para registrar y controlar temperaturas de productos
        en los siguientes procesos:
        - Recepciones de productos (por lote)
        - Inventarios físicos
        - Órdenes de fabricación (Manufacturing)
    """,
    'author': 'Mikipu SAC',
    'depends': [
        'stock',
        'mrp',
        'mail',
    ],
    'data': [
        'security/stock_temperature_security.xml',
        'security/ir.model.access.csv',
        'data/stock_temperature_data.xml',
        'views/stock_temperature_log_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_inventory_views.xml',
        'views/mrp_production_views.xml',
        'views/menu_views.xml',
        'wizards/stock_temperature_wizard_views.xml',
        'report/stock_temperature_report_templates.xml',
        'report/stock_temperature_report_actions.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
