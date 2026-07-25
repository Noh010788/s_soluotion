from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        check_company=True,
        copy=False,
        index=True,
        ondelete='set null',
    )


class StockMove(models.Model):
    _inherit = 'stock.move'

    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        check_company=True,
        copy=False,
        index=True,
        ondelete='cascade',
    )
    maintenance_billable = fields.Boolean(
        string='Bill Customer',
        default=True,
        help='Include this spare part in the customer quotation.',
    )
    maintenance_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    maintenance_line_cost = fields.Monetary(
        string='Part Cost',
        currency_field='maintenance_currency_id',
        compute='_compute_maintenance_line_cost',
    )

    @api.depends(
        'state',
        'quantity',
        'product_uom_qty',
        'product_id.standard_price',
        'stock_valuation_layer_ids.value',
    )
    def _compute_maintenance_line_cost(self):
        for move in self:
            valuation = abs(sum(move.stock_valuation_layer_ids.mapped('value')))
            quantity = (
                move.quantity
                if move.state in ('done', 'cancel')
                else move.product_uom_qty
            )
            move.maintenance_line_cost = (
                valuation
                if valuation
                else quantity * move.product_id.standard_price
            )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            request_id = values.get('maintenance_request_id')
            if not request_id:
                continue
            request = self.env['maintenance.request'].browse(request_id).exists()
            if not request:
                continue
            repair = request._get_or_create_spare_parts_repair()
            if values.get('repair_id') and values['repair_id'] != repair.id:
                raise ValidationError(_(
                    'A maintenance spare part cannot be linked to another repair order.'
                ))
            values.update({
                'repair_id': repair.id,
                'repair_line_type': 'add',
                'company_id': request.company_id.id,
                'location_id': repair.location_id.id,
                'location_dest_id': repair.location_dest_id.id,
            })
            values.setdefault('product_uom_qty', 1.0)
            product = self.env['product.product'].browse(
                values.get('product_id')
            ).exists()
            if product:
                values.setdefault('product_uom', product.uom_id.id)
                values.setdefault('price_unit', product.lst_price)
        return super().create(vals_list)

    def write(self, vals):
        protected_fields = {
            'maintenance_request_id', 'repair_id', 'repair_line_type',
            'company_id', 'location_id', 'location_dest_id', 'product_id',
            'product_uom', 'product_uom_qty',
        }
        locked_moves = self.filtered(
            lambda move: move.maintenance_request_id
            and move.repair_id.state not in ('draft', 'cancel')
        )
        if locked_moves and protected_fields.intersection(vals):
            raise ValidationError(_(
                'Reserved or issued maintenance spare-part lines cannot be changed.'
            ))
        return super().write(vals)

    def unlink(self):
        locked_moves = self.filtered(
            lambda move: move.maintenance_request_id
            and move.repair_id.state not in ('draft', 'cancel')
        )
        if locked_moves:
            raise ValidationError(_(
                'Return or consume reserved spare parts before deleting them.'
            ))
        return super().unlink()

    @api.constrains('maintenance_request_id', 'product_id')
    def _check_maintenance_spare_part_category(self):
        spare_category = self.env.ref(
            'rental_product_maintenance.product_category_spare_parts',
            raise_if_not_found=False,
        )
        if not spare_category:
            return
        for move in self.filtered('maintenance_request_id'):
            category_path = [
                int(category_id)
                for category_id in (move.product_id.categ_id.parent_path or '').split('/')
                if category_id
            ]
            if spare_category.id not in category_path:
                raise ValidationError(_(
                    '%(product)s is not in the Spare Parts product category.',
                    product=move.product_id.display_name,
                ))
            if not move.product_id.is_storable:
                raise ValidationError(_(
                    '%(product)s must be a storable product to be used as a spare part.',
                    product=move.product_id.display_name,
                ))

    @api.constrains(
        'maintenance_request_id', 'repair_id', 'company_id',
        'location_id', 'location_dest_id',
    )
    def _check_maintenance_repair_consistency(self):
        for move in self.filtered('maintenance_request_id'):
            request = move.maintenance_request_id
            repair = request.repair_order_id
            if (
                not repair
                or move.repair_id != repair
                or repair.maintenance_request_id != request
                or move.company_id != request.company_id
                or move.location_id != repair.location_id
                or move.location_dest_id != repair.location_dest_id
            ):
                raise ValidationError(_(
                    'The spare part, maintenance request, repair order and stock locations must match.'
                ))
    def _create_repair_sale_order_line(self):
        excluded = self.filtered(
            lambda move: move.maintenance_request_id
            and (
                not move.maintenance_billable
                or float_is_zero(
                    move.quantity if move.state == 'done' else move.product_uom_qty,
                    precision_rounding=move.product_uom.rounding,
                )
            )
        )
        return super(StockMove, self - excluded)._create_repair_sale_order_line()
