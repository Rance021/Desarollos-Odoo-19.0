# -*- coding: utf-8 -*-
"""
mrp_bom.py
──────────
Agrega el campo byproduct_cost_method a mrp.bom para que el método de
reparto de costos se configure una vez en la lista de materiales y se
propague automáticamente a cada orden de fabricación generada.
"""
from odoo import api, fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    byproduct_cost_method = fields.Selection(
        selection=[
            ('uom_normalized', 'Proporcional a Cantidad (UdM Normalizada)'),
            ('raw_qty',        'Proporcional a Cantidad (sin conversión)'),
            ('manual',         'Manual'),
        ],
        string='Método de Reparto de Costos',
        default='uom_normalized',
        help=(
            'El método seleccionado se propagará a las órdenes de fabricación '
            'creadas a partir de esta lista de materiales.'
        ),
    )


class MrpProductionBomPropagation(models.Model):
    """
    Propagación del método de reparto desde la BoM a mrp.production.
    Separado en un modelo _inherit para mantener mrp_bom.py limpio.
    """
    _inherit = 'mrp.production'

    @api.onchange('bom_id')
    def _onchange_bom_id_propagate_cost_method(self):
        """Propaga el método de la BoM al seleccionarla en la orden."""
        if self.bom_id:
            self.byproduct_cost_method = (
                self.bom_id.byproduct_cost_method or 'uom_normalized'
            )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Al crear la orden programáticamente (ej: MRP planificador),
        propaga el método desde la BoM si no viene en los valores.
        """
        productions = super().create(vals_list)
        for prod in productions:
            if prod.bom_id and not prod.byproduct_cost_method:
                prod.byproduct_cost_method = (
                    prod.bom_id.byproduct_cost_method or 'uom_normalized'
                )
        return productions
