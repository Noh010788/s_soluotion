from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _action_done(self):
        self._check_negative_stock_block()
        return super()._action_done()

    def _check_negative_stock_block(self):
        if self.env.context.get('allow_negative_stock'):
            return

        quantities_by_key = defaultdict(float)
        lines_by_key = {}
        for line in self:
            company = line.company_id or line.env.company
            if not company.block_negative_stock:
                continue
            if not line.product_id.is_storable:
                continue
            if line.location_id.usage not in ('internal', 'transit'):
                continue
            if float_is_zero(line.quantity_product_uom, precision_rounding=line.product_id.uom_id.rounding):
                continue

            key = (
                line.product_id.id,
                line.location_id.id,
                line.lot_id.id or False,
                line.package_id.id or False,
                line.owner_id.id or False,
                company.id,
            )
            quantities_by_key[key] += line.quantity_product_uom
            lines_by_key[key] = line

        errors = []
        Quant = self.env['stock.quant'].sudo()
        for key, requested_qty in quantities_by_key.items():
            line = lines_by_key[key]
            quants = Quant._gather(
                line.product_id,
                line.location_id,
                lot_id=line.lot_id,
                package_id=line.package_id,
                owner_id=line.owner_id,
                strict=True,
            )
            on_hand_qty = sum(quants.mapped('quantity'))
            rounding = line.product_id.uom_id.rounding
            if float_compare(on_hand_qty - requested_qty, 0.0, precision_rounding=rounding) < 0:
                errors.append(_(
                    '%(product)s at %(location)s: available %(available)s %(uom)s, requested %(requested)s %(uom)s',
                    product=line.product_id.display_name,
                    location=line.location_id.display_name,
                    available=on_hand_qty,
                    requested=requested_qty,
                    uom=line.product_id.uom_id.name,
                ))

        if errors:
            raise UserError(_(
                'Negative stock is blocked by Inventory Settings.\n\n%(lines)s',
                lines='\n'.join(errors),
            ))
