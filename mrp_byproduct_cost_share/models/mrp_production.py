# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round, float_is_zero

_logger = logging.getLogger(__name__)

_QTY_PREC   = 6
_SHARE_PREC = 2


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    byproduct_cost_share_auto = fields.Boolean(
        string='Recalcular cost_share automáticamente',
        default=True,
        help=(
            'Si está activo, el cost_share de los subproductos se recalcula '
            'automáticamente al modificar cantidades y al validar la orden. '
            'Desactivar para gestionar el reparto de costos de forma manual.'
        ),
    )

    def _compute_byproduct_cost_share(self):
        self.ensure_one()

        byproducts = self.move_byproduct_ids.filtered(
            lambda m: m.state not in ('cancel',)
        )

        if not byproducts:
            return

        if len(byproducts) == 1:
            byproducts.cost_share = 100.0
            return

        moves      = list(byproducts)
        quantities = [self._qty_for_cost_share(m) for m in moves]
        total_qty  = sum(quantities)

        if float_is_zero(total_qty, precision_digits=_QTY_PREC):
            raise UserError(_(
                "No se puede calcular el reparto de costos para «%s»: "
                "la cantidad total de subproductos es cero. "
                "Verifique que los subproductos tengan cantidad > 0.",
                self.name,
            ))

        # Resetear a 0 antes de asignar para evitar que la validación nativa
        # (suma <= 100) falle durante la redistribución parcial.
        for move in moves:
            move.cost_share = 0.0

        accumulated = 0.0
        last = len(moves) - 1

        for i, (move, qty) in enumerate(zip(moves, quantities)):
            if i < last:
                share = float_round(
                    (qty / total_qty) * 100.0,
                    precision_digits=_SHARE_PREC,
                )
                accumulated += share
            else:
                share = float_round(
                    100.0 - accumulated,
                    precision_digits=_SHARE_PREC,
                )
            move.cost_share = share
            _logger.debug(
                '[%s] %s → %g %s = %.2f%%',
                self.name, move.product_id.name,
                qty, move.product_uom.name, share,
            )

    def _qty_for_cost_share(self, move):
        """
        Retorna la cantidad real producida (move.quantity) normalizada
        a la UdM raíz del árbol jerárquico (Odoo 19).

        Fallback a move.product_uom_qty si quantity == 0.
        """
        qty = (
            move.quantity
            if not float_is_zero(move.quantity, precision_digits=_QTY_PREC)
            else move.product_uom_qty
        )

        if float_is_zero(qty, precision_digits=_QTY_PREC):
            return 0.0

        source_uom = move.product_uom
        if not source_uom or not source_uom.relative_uom_id:
            return qty

        try:
            parts = [p for p in (source_uom.parent_path or '').split('/') if p]
            if len(parts) < 2:
                return qty

            root_uom = self.env['uom.uom'].browse(int(parts[0]))
            if not root_uom.exists():
                return qty

            return source_uom._compute_quantity(qty, root_uom, raise_if_failure=False)

        except Exception:
            _logger.warning(
                '[%s] No se pudo convertir UdM para "%s". Usando cantidad cruda.',
                self.name, move.product_id.name,
            )
            return qty

    def button_mark_done(self):
        for prod in self:
            if prod.byproduct_cost_share_auto and prod.move_byproduct_ids.filtered(
                lambda m: m.state not in ('cancel',)
            ):
                try:
                    prod._compute_byproduct_cost_share()
                except UserError as e:
                    _logger.warning(
                        '[%s] No se recalculó cost_share al validar: %s',
                        prod.name, e,
                    )
        return super().button_mark_done()


class StockMoveByproductCostShare(models.Model):
    _inherit = 'stock.move'

    def _get_byproduct_production(self):
        """
        Retorna la orden de fabricación si este move es un subproducto
        con recálculo automático activo, sino False.
        """
        production = self.production_id
        if (
            production
            and production.byproduct_cost_share_auto
            # Solo actuar en moves que son subproductos (no componentes)
            and self in production.move_byproduct_ids
        ):
            return production
        return False

    @api.model_create_multi
    def create(self, vals_list):
        """
        Tras crear moves, recalcula cost_share en las órdenes afectadas.
        Cubre el caso de agregar una línea nueva en subproductos y guardar.
        """
        moves = super().create(vals_list)
        productions = moves.mapped('production_id').filtered(
            lambda p: p.byproduct_cost_share_auto
        )
        for prod in productions:
            try:
                prod._compute_byproduct_cost_share()
            except UserError as e:
                _logger.warning(
                    '[%s] No se recalculó cost_share al crear move: %s',
                    prod.name, e,
                )
        return moves

    def write(self, vals):
        """
        Tras escribir cambios en quantity o product_uom_qty,
        recalcula cost_share en las órdenes afectadas.
        Cubre el caso de editar cantidades en líneas existentes.
        """
        result = super().write(vals)
        if any(f in vals for f in ('quantity', 'product_uom_qty', 'product_uom')):
            productions = self.mapped('production_id').filtered(
                lambda p: p.byproduct_cost_share_auto
            )
            for prod in productions:
                try:
                    prod._compute_byproduct_cost_share()
                except UserError as e:
                    _logger.warning(
                        '[%s] No se recalculó cost_share al escribir move: %s',
                        prod.name, e,
                    )
        return result
