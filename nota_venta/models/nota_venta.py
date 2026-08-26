from odoo import models, fields, api


class NotaVenta(models.Model):
    _inherit = 'account.move'

    is_nota_venta = fields.Boolean(
        string='Es Nota de Venta',
        compute='_compute_is_nota_venta',
        store=True,
    )

    @api.depends('journal_id')
    def _compute_is_nota_venta(self):
        for move in self:
            move.is_nota_venta = bool(
                move.journal_id and move.journal_id.code == 'NV'
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_is_nota_venta'):
            journal = self.env['account.journal'].search(
                [('code', '=', 'NV'), ('company_id', '=', self.env.company.id)],
                limit=1
            )
            if journal:
                res['journal_id'] = journal.id
        return res
