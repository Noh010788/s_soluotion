from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    order_type = fields.Selection(
        selection=[
            ('sale', 'Sale'),
            ('rental', 'Rental'),
        ],
        string='Type',
        default='sale',
        required=True,
        index=True,
        copy=False,
    )

    is_rental_order = fields.Boolean(
        string='Rental Order',
        compute='_compute_is_rental_order',
        store=True,
    )
    rental_status = fields.Selection(
        selection=[
            ('quotation', 'Rental Quotation'),
            ('quotation_sent', 'Rental Quotation Sent'),
            ('rental_order', 'Rental Order'),
            ('returned', 'Returned'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        compute='_compute_rental_status',
        store=True,
    )
    rental_due_datetime = fields.Datetime(
        string='Rental Due Date',
        compute='_compute_rental_dates',
        store=True,
    )
    rental_remain_days = fields.Float(
        string='Remain Rental',
        compute='_compute_rental_dates',
    )
    rental_remain_label = fields.Char(
        string='Remain Rental',
        compute='_compute_rental_dates',
    )
    rental_returned = fields.Boolean(
        string='Returned',
        copy=False,
        tracking=True,
    )

    @api.depends('order_type')
    def _compute_is_rental_order(self):
        for order in self:
            order.is_rental_order = order.order_type == 'rental'

    @api.depends('state', 'order_type', 'rental_returned')
    def _compute_rental_status(self):
        for order in self:
            if order.order_type != 'rental':
                order.rental_status = False
            elif order.rental_returned:
                order.rental_status = 'returned'
            elif order.state == 'draft':
                order.rental_status = 'quotation'
            elif order.state == 'sent':
                order.rental_status = 'quotation_sent'
            elif order.state == 'sale':
                order.rental_status = 'rental_order'
            elif order.state == 'cancel':
                order.rental_status = 'cancel'
            else:
                order.rental_status = False

    @api.depends('order_line.rental_end_datetime', 'order_type', 'rental_returned')
    def _compute_rental_dates(self):
        now = fields.Datetime.now()
        for order in self:
            rental_end_dates = order.order_line.filtered('rental_end_datetime').mapped('rental_end_datetime')
            order.rental_due_datetime = max(rental_end_dates) if order.order_type == 'rental' and rental_end_dates else False
            remain_days = (
                max((order.rental_due_datetime - now).total_seconds() / 86400, 0.0)
                if order.rental_due_datetime and not order.rental_returned
                else 0.0
            )
            order.rental_remain_days = remain_days
            if order.rental_returned:
                order.rental_remain_label = _('Returned')
            elif not order.rental_due_datetime:
                order.rental_remain_label = ''
            elif not remain_days:
                order.rental_remain_label = _('Due')
            else:
                order.rental_remain_label = _('%s Days') % round(remain_days, 2)

    def _get_returnable_rental_pickings(self):
        self.ensure_one()
        return self.picking_ids.filtered(
            lambda picking: picking.state == 'done'
            and picking.picking_type_code == 'outgoing'
            and not any(picking.move_ids.mapped('origin_returned_move_id'))
            and picking._can_return()
        )

    def _get_rental_stock_location(self):
        self.ensure_one()
        warehouse = self.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        rental_location = self.env['stock.location'].search([
            ('name', '=', 'Rental Stock'),
            ('usage', '=', 'internal'),
            ('id', 'child_of', warehouse.view_location_id.id),
        ], limit=1)
        if not rental_location:
            raise UserError(_("Please configure the WH/Rental Stock location first."))
        return rental_location

    def _use_rental_stock_location(self):
        for order in self.filtered(lambda so: so.order_type == 'rental'):
            rental_location = order._get_rental_stock_location()
            pickings = order.picking_ids.filtered(
                lambda picking: picking.picking_type_code == 'outgoing'
                and not picking.return_id
                and picking.state not in ('done', 'cancel')
            )
            for picking in pickings:
                if picking.state == 'assigned':
                    picking.do_unreserve()
                picking.write({'location_id': rental_location.id})
                picking.move_ids.filtered(lambda move: move.state not in ('done', 'cancel')).write({
                    'location_id': rental_location.id,
                })
                picking.move_line_ids.filtered(lambda line: line.state not in ('done', 'cancel')).write({
                    'location_id': rental_location.id,
                })
                picking.action_assign()

    def action_rental_return(self):
        all_return_pickings = self.env['stock.picking']
        for order in self:
            if order.order_type != 'rental':
                raise UserError(_("Return is only available for rental orders."))
            if order.state != 'sale':
                raise UserError(_("Only confirmed rental orders can be returned."))
            if order.rental_returned:
                raise UserError(_("This rental order is already returned."))

            return_pickings = self.env['stock.picking']
            for picking in order._get_returnable_rental_pickings():
                wizard = self.env['stock.return.picking'].with_context(
                    active_id=picking.id,
                    active_ids=picking.ids,
                    active_model='stock.picking',
                ).create({'picking_id': picking.id})
                action = wizard.action_create_returns_all()
                return_picking = self.env['stock.picking'].browse(action['res_id'])
                for move in return_picking.move_ids:
                    move.quantity = move.product_uom_qty
                    move.picked = True
                validate_action = return_picking.with_context(skip_backorder=True).button_validate()
                if isinstance(validate_action, dict):
                    if validate_action.get('res_model') == 'stock.immediate.transfer':
                        wizard = self.env[validate_action['res_model']].browse(validate_action['res_id'])
                        wizard.process()
                    elif validate_action.get('res_model') == 'stock.backorder.confirmation':
                        wizard = self.env[validate_action['res_model']].browse(validate_action['res_id'])
                        wizard.process()
                return_pickings |= return_picking

            if not return_pickings:
                raise UserError(_("There are no delivered rental products left to return."))

            order.rental_returned = True
            order.message_post(body=_("Rental products were returned to stock: %s") % ', '.join(return_pickings.mapped('name')))
            all_return_pickings |= return_pickings

        if len(all_return_pickings) == 1:
            return {
                'name': _('Returned Picking'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': all_return_pickings.id,
                'view_mode': 'form',
            }
        return {
            'name': _('Returned Pickings'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'domain': [('id', 'in', all_return_pickings.ids)],
            'view_mode': 'list,form',
        }

    def init(self):
        self.env.cr.execute(
            """
            UPDATE sale_order
               SET order_type = 'sale'
             WHERE order_type IS NULL
            """
        )

    def action_confirm(self):
        action = super().action_confirm()
        self._use_rental_stock_location()
        return action


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    order_type = fields.Selection(related='order_id.order_type', store=True)
    rental_type = fields.Selection(
        selection=[
            ('hour', 'Hour'),
            ('day', 'Day'),
            ('week', 'Week'),
            ('month', 'Month'),
        ],
        string='Rental Type',
        default='day',
        copy=True,
    )
    rental_start_datetime = fields.Datetime(
        string='Start Date',
        copy=True,
    )
    rental_end_datetime = fields.Datetime(
        string='End Date',
        compute='_compute_rental_end_datetime',
        store=True,
        readonly=False,
        copy=True,
    )
    rental_qty = fields.Float(
        string='Qty of Rent',
        default=1.0,
        copy=True,
    )

    def _get_rental_minimum_qty(self):
        self.ensure_one()
        product = self.product_id.product_tmpl_id
        minimum_qty = {
            'hour': product.rental_min_hours,
            'day': product.rental_min_days,
            'week': product.rental_min_weeks,
            'month': product.rental_min_months,
        }.get(self.rental_type or 'day', product.rental_min_days)
        return minimum_qty or 1.0

    def _get_rental_delta(self):
        self.ensure_one()
        rental_qty = self.rental_qty or 0.0
        if self.rental_type == 'hour':
            return timedelta(hours=rental_qty)
        if self.rental_type == 'week':
            return timedelta(weeks=rental_qty)
        if self.rental_type == 'month':
            whole_months = int(rental_qty)
            remaining_days = (rental_qty - whole_months) * 30
            return relativedelta(months=whole_months, days=remaining_days)
        return timedelta(days=rental_qty)

    @api.depends('rental_start_datetime', 'rental_qty', 'rental_type')
    def _compute_rental_end_datetime(self):
        for line in self:
            if (
                line.order_id.order_type == 'rental'
                and line.rental_start_datetime
                and line.rental_qty
            ):
                line.rental_end_datetime = line.rental_start_datetime + line._get_rental_delta()
            elif not line.rental_start_datetime:
                line.rental_end_datetime = False

    def _get_rental_price(self):
        self.ensure_one()
        product = self.product_id.product_tmpl_id
        return {
            'hour': product.rental_price_per_hour,
            'day': product.rental_price_per_day,
            'week': product.rental_price_per_week,
            'month': product.rental_price_per_month,
        }.get(self.rental_type or 'day', product.rental_price_per_day)

    def _get_display_price(self):
        self.ensure_one()
        if (
            self.order_id.order_type == 'rental'
            and self.product_id
            and self.product_id.product_tmpl_id.is_rental
        ):
            return self._get_rental_price() * (self.rental_qty or 1.0)
        return super()._get_display_price()

    @api.onchange('rental_type')
    def _onchange_rental_type(self):
        if self.order_id.order_type == 'rental' and self.product_id:
            self.rental_qty = self._get_rental_minimum_qty()
            self._compute_rental_end_datetime()
            self._reset_price_unit()

    @api.onchange('product_id')
    def _onchange_product_id_rental_price(self):
        if self.order_id.order_type == 'rental' and self.product_id:
            self.rental_qty = self._get_rental_minimum_qty()
            self._compute_rental_end_datetime()
            self._reset_price_unit()

    @api.onchange('rental_start_datetime', 'rental_qty', 'rental_type')
    def _onchange_rental_period(self):
        for line in self:
            line._compute_rental_end_datetime()
            if line.order_id.order_type == 'rental' and line.product_id:
                line._reset_price_unit()
