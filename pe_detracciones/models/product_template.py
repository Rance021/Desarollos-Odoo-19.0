from odoo import models


class ProductTemplate(models.Model):
    """No redeclaramos l10n_pe_withhold_code ni l10n_pe_withhold_percentage.
    Esos campos ya los define l10n_pe correctamente (Many2one y Float).
    Este archivo solo existe para futuras extensiones si se necesitan."""
    _inherit = 'product.template'
