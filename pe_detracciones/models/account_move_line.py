from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_es_linea_detraccion = fields.Boolean(
        string='Es línea de detracción',
        default=False,
        copy=False,
        help='Marca interna: esta línea es un asiento contable de detracción SUNAT, '
             'no una línea de factura electrónica. Excluida de validaciones EDI.',
    )

    def _check_edi_line_tax_required(self):
        """Override: las líneas de detracción son asientos contables puros
        (CxC ↔ Cuenta Detracciones). No llevan impuesto y no deben ser
        validadas por l10n_pe_edi como líneas de factura electrónica."""
        if self.x_es_linea_detraccion:
            return False
        return super()._check_edi_line_tax_required()
