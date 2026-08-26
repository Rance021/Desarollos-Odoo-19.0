{
    'name': 'Mikipu - CC Automático en Facturas',
    'version': '19.0.1.0.0',
    'summary': 'Agrega contactos del cliente en CC al enviar facturas',
    'description': """
        Permite marcar contactos de un cliente como "Recibe facturas",
        y al enviar una factura, estos se agregan automáticamente en CC.
    """,
    'author': 'Mikipu SAC',
    'category': 'Accounting',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
