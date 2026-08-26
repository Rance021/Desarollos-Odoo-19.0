from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    invoice_cc = fields.Boolean(
        string='Recibe facturas por correo (CC)',
        default=False,
        help='Si está marcado, este contacto será agregado en CC '
             'al enviar facturas del cliente al que pertenece.',
    )
