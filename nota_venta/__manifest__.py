{
    'name': 'Nota de Ventas',
    'version': '19.0.1.1.0',
    'summary': 'Notas de Ventas con diario NV y boton en Ordenes de Venta',
    'category': 'Accounting',
    'depends': ['account', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_journal_data.xml',
        'views/nota_venta_views.xml',
        'views/nota_venta_menus.xml',
        'views/sale_order_nota_venta_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
