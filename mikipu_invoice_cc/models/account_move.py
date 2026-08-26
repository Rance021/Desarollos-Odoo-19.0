from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_invoice_cc_partners(self):
        """
        Retorna contactos del cliente con invoice_cc=True y email definido.
        Solo aplica a facturas y notas de crédito de venta.
        """
        self.ensure_one()
        if not self.partner_id:
            return self.env['res.partner']

        root_partner = self.partner_id.commercial_partner_id

        return self.env['res.partner'].search([
            ('parent_id', '=', root_partner.id),
            ('invoice_cc', '=', True),
            ('email', '!=', False),
            ('email', '!=', ''),
            ('active', '=', True),
        ])


class AccountMoveSend(models.AbstractModel):
    """
    account.move.send es AbstractModel en Odoo 19.
    Lo heredamos también como AbstractModel para poder override
    _get_default_mail_partner_ids e inyectar los CC automáticamente.
    """
    _inherit = 'account.move.send'

    def _get_default_mail_partner_ids(self, move, mail_template, mail_lang):
        """
        Extiende los destinatarios base con los contactos CC del cliente.
        """
        partners = super()._get_default_mail_partner_ids(
            move, mail_template, mail_lang
        )

        if move.move_type not in ('out_invoice', 'out_refund'):
            return partners

        cc_partners = move._get_invoice_cc_partners()
        if cc_partners:
            partners |= cc_partners

        return partners
