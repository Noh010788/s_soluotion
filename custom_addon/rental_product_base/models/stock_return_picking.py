from odoo import _, models
from odoo.exceptions import UserError


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _check_not_returning_rental_return(self):
        for wizard in self:
            picking = wizard.picking_id
            if (
                picking.sale_id.order_type == 'rental'
                and picking.return_id
                and picking.picking_type_code == 'incoming'
            ):
                raise UserError(_(
                    "This picking is already the return of rental order %s. "
                    "Returning it again would create another outgoing delivery."
                ) % picking.sale_id.display_name)

    def action_create_returns(self):
        self._check_not_returning_rental_return()
        return super().action_create_returns()

    def action_create_returns_all(self):
        self._check_not_returning_rental_return()
        return super().action_create_returns_all()

    def _prepare_picking_default_values_based_on(self, picking):
        vals = super()._prepare_picking_default_values_based_on(picking)
        if (
            picking.sale_id.order_type == 'rental'
            and picking.picking_type_code == 'outgoing'
            and not picking.return_id
        ):
            vals['location_dest_id'] = picking.sale_id._get_rental_stock_location().id
        return vals
