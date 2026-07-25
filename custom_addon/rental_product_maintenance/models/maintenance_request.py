from odoo import _, models, fields, api
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero
from datetime import timedelta


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    maintenance_type = fields.Selection(
        selection=[
            ('corrective', 'Breakdown'),
            ('preventive', 'Preventive'),
        ],
        string='Maintenance Type',
        default='corrective',
    )

    rental_product_id = fields.Many2one(
        'product.product',
        string="Rental Product",
        domain="[('product_tmpl_id.is_rental','=',True)]"
    )
    rental_customer_id = fields.Many2one(
        'res.partner',
        string="Customer",
        domain="[('customer_rank', '>', 0)]",
    )
    rental_order_id = fields.Many2one(
        'sale.order',
        string="Rental Order",
        domain="[('order_type', '=', 'rental')]",
    )
    rental_order_line_id = fields.Many2one(
        'sale.order.line',
        string="Rental Order Line",
        domain="[('order_id', '=', rental_order_id), ('order_id.order_type', '=', 'rental')]",
    )
    rental_unit_number = fields.Integer(
        string="Rental Unit",
        default=1,
        copy=False,
        help="Unit sequence from the rented quantity on the rental order line.",
    )
    customer_accepted = fields.Boolean(
        string="Customer Accepted",
        copy=False,
        readonly=True,
    )
    customer_signature = fields.Image(
        string="Customer Signature",
        copy=False,
        readonly=True,
        max_width=1024,
        max_height=512,
    )
    customer_signed_by = fields.Char(
        string="Signed By",
        copy=False,
        readonly=True,
    )
    customer_signed_on = fields.Datetime(
        string="Signed On",
        copy=False,
        readonly=True,
    )
    repair_order_id = fields.Many2one(
        'repair.order',
        string='Parts Repair Order',
        check_company=True,
        copy=False,
        readonly=True,
    )
    spare_part_move_ids = fields.One2many(
        'stock.move',
        'maintenance_request_id',
        string='Used Spare Parts',
        domain=[('repair_line_type', '=', 'add')],
        copy=False,
    )
    parts_under_warranty = fields.Boolean(
        string='Parts Under Warranty',
        help='Billable spare parts have a zero sale price when under warranty.',
    )
    parts_state = fields.Selection(
        selection=[
            ('none', 'No Parts'),
            ('draft', 'Draft'),
            ('confirmed', 'Reserved'),
            ('under_repair', 'Issued / In Use'),
            ('done', 'Consumed'),
            ('cancel', 'Cancelled'),
        ],
        string='Parts Status',
        compute='_compute_parts_state',
    )
    parts_sale_order_id = fields.Many2one(
        'sale.order',
        string='Parts Quotation',
        related='repair_order_id.sale_order_id',
        readonly=True,
        store=True,
    )
    spare_parts_category_id = fields.Many2one(
        'product.category',
        compute='_compute_spare_parts_master_data',
    )
    spare_parts_source_location_id = fields.Many2one(
        'stock.location',
        string='Spare Parts Location',
        compute='_compute_spare_parts_master_data',
    )
    spare_parts_consumption_location_id = fields.Many2one(
        'stock.location',
        string='Maintenance Consumption',
        compute='_compute_spare_parts_master_data',
    )
    spare_parts_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    spare_parts_cost = fields.Monetary(
        string='Spare Parts Cost',
        currency_field='spare_parts_currency_id',
        compute='_compute_spare_parts_totals',
    )
    spare_part_count = fields.Integer(
        string='Spare Parts',
        compute='_compute_spare_parts_totals',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_rental_reference_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._sync_rental_reference_vals(vals)
        if 'stage_id' in vals:
            done_stage = self.env['maintenance.stage'].browse(vals['stage_id'])
            if done_stage.done:
                unfinished_parts = self.filtered(
                    lambda request: request.spare_part_move_ids
                    and request.parts_state not in ('done', 'cancel')
                )
                if unfinished_parts:
                    raise UserError(_(
                        'Consume or return all spare parts before marking the maintenance request Done.'
                    ))
                if not self.env.context.get('skip_maintenance_customer_signature'):
                    unsigned_requests = self.filtered(lambda request: not request.customer_accepted or not request.customer_signature)
                    if unsigned_requests:
                        raise UserError(_("Customer must accept and sign before this maintenance request can be marked Done."))
        result = super().write(vals)
        if 'parts_under_warranty' in vals:
            self.mapped('repair_order_id').write({
                'under_warranty': vals['parts_under_warranty'],
            })
        return result

    @api.depends('repair_order_id.state', 'spare_part_move_ids')
    def _compute_parts_state(self):
        for request in self:
            request.parts_state = (
                request.repair_order_id.state
                if request.repair_order_id
                else 'none'
            )

    @api.depends_context('company')
    def _compute_spare_parts_master_data(self):
        category = self.env.ref(
            'rental_product_maintenance.product_category_spare_parts',
            raise_if_not_found=False,
        )
        source_location = self.env.ref(
            'rental_product_maintenance.stock_location_spare_parts',
            raise_if_not_found=False,
        )
        consumption_location = self.env.ref(
            'rental_product_maintenance.stock_location_maintenance_consumption',
            raise_if_not_found=False,
        )
        for request in self:
            request.spare_parts_category_id = category
            request.spare_parts_source_location_id = source_location
            request.spare_parts_consumption_location_id = consumption_location

    @api.depends(
        'spare_part_move_ids',
        'spare_part_move_ids.maintenance_line_cost',
    )
    def _compute_spare_parts_totals(self):
        for request in self:
            request.spare_part_count = len(request.spare_part_move_ids)
            request.spare_parts_cost = sum(
                request.spare_part_move_ids.mapped('maintenance_line_cost')
            )

    def _get_or_create_spare_parts_repair(self):
        self.ensure_one()
        self._check_spare_parts_access()
        if self.repair_order_id:
            if self.repair_order_id.state != 'draft':
                raise UserError(_(
                    'Spare-part lines cannot be changed after they have been reserved.'
                ))
            return self.repair_order_id

        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not warehouse:
            raise UserError(_(
                'Configure a warehouse for the company first.'
            ))

        picking_type = self.env.ref(
            'rental_product_maintenance.picking_type_maintenance_spare_parts',
            raise_if_not_found=False,
        )
        if not picking_type or picking_type.company_id != self.company_id:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'repair_operation'),
                ('warehouse_id', '=', warehouse.id),
                ('default_location_src_id.name', '=', 'Spare Parts'),
            ], limit=1)
        if not picking_type:
            raise UserError(_(
                'Configure the Maintenance Spare Parts operation type first.'
            ))

        source_location = self.env.ref(
            'rental_product_maintenance.stock_location_spare_parts',
            raise_if_not_found=False,
        )
        if not source_location or source_location.company_id != self.company_id:
            source_location = self.env['stock.location'].search([
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('name', '=', 'Spare Parts'),
                ('usage', '=', 'internal'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not source_location:
            raise UserError(_('The Spare Parts stock location is not configured.'))

        partner = self.rental_customer_id or self.rental_order_id.partner_id
        repair = self.env['repair.order'].create({
            'company_id': self.company_id.id,
            'partner_id': partner.id,
            'user_id': (self.user_id or self.env.user).id,
            'schedule_date': self.schedule_date or fields.Datetime.now(),
            'under_warranty': self.parts_under_warranty,
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'internal_notes': _(
                '<p>Spare parts for Maintenance Request: %(request)s</p>',
                request=self.display_name,
            ),
            'maintenance_request_id': self.id,
        })
        self.repair_order_id = repair
        return repair

    def _check_spare_parts_access(self):
        if not self.env.user.has_group(
            'rental_product_maintenance.group_maintenance_spare_parts_user'
        ):
            raise AccessError(_(
                'You are not allowed to manage maintenance spare parts.'
            ))

    def action_reserve_spare_parts(self):
        self.ensure_one()
        self._check_spare_parts_access()
        if not self.spare_part_move_ids:
            raise UserError(_('Add at least one spare part first.'))
        invalid_moves = self.spare_part_move_ids.filtered(
            lambda move: float_compare(
                move.product_uom_qty,
                0.0,
                precision_rounding=move.product_uom.rounding,
            ) <= 0
        )
        if invalid_moves:
            raise UserError(_('Planned spare-part quantities must be greater than zero.'))

        repair = self._get_or_create_spare_parts_repair()
        repair.action_validate()
        repair.action_assign()

        unavailable = repair.move_ids.filtered(
            lambda move: move.repair_line_type == 'add'
            and float_compare(
                move.quantity,
                move.product_uom_qty,
                precision_rounding=move.product_uom.rounding,
            ) < 0
        )
        if unavailable:
            detail_pattern = _(
                '%(product)s: available %(available)s, required %(required)s %(uom)s'
            )
            details = '\n'.join(
                detail_pattern % {
                    'product': move.product_id.display_name,
                    'available': move.quantity,
                    'required': move.product_uom_qty,
                    'uom': move.product_uom.name,
                }
                for move in unavailable
            )
            raise UserError(_(
                'Not enough stock in the Spare Parts location.\n\n%(details)s',
                details=details,
            ))
        self.message_post(body=_('Spare parts reserved from the Spare Parts location.'))
        return True

    def action_issue_spare_parts(self):
        self.ensure_one()
        self._check_spare_parts_access()
        if not self.repair_order_id or self.repair_order_id.state != 'confirmed':
            raise UserError(_('Reserve the spare parts before issuing them.'))
        self.repair_order_id.action_repair_start()
        self.message_post(body=_('Reserved spare parts issued to this maintenance job.'))
        return True

    def action_return_spare_parts(self):
        self.ensure_one()
        self._check_spare_parts_access()
        repair = self.repair_order_id
        if not repair or repair.state not in ('confirmed', 'under_repair'):
            raise UserError(_('Only reserved or issued spare parts can be returned.'))
        repair.action_unreserve()
        repair.action_repair_cancel()
        self.message_post(body=_('Unused spare parts returned to available stock.'))
        return True

    def action_consume_spare_parts(self):
        self.ensure_one()
        self._check_spare_parts_access()
        repair = self.repair_order_id
        if not repair or repair.state != 'under_repair':
            raise UserError(_('Issue the spare parts before consuming them.'))

        for move in self.spare_part_move_ids:
            if float_compare(
                move.quantity,
                move.product_uom_qty,
                precision_rounding=move.product_uom.rounding,
            ) > 0:
                raise UserError(_(
                    'Used quantity cannot exceed planned quantity for %(product)s.',
                    product=move.product_id.display_name,
                ))
            move.picked = not float_is_zero(
                move.quantity,
                precision_rounding=move.product_uom.rounding,
            )
        repair.action_repair_end()
        self.message_post(body=_('Actual spare-part quantities consumed from stock.'))
        return True

    def action_create_spare_parts_quotation(self):
        self.ensure_one()
        self._check_spare_parts_access()
        repair = self.repair_order_id
        if not repair or repair.state != 'done':
            raise UserError(_('Consume the spare parts before creating a quotation.'))
        billable_moves = self.spare_part_move_ids.filtered(
            lambda move: move.maintenance_billable
            and not float_is_zero(
                move.quantity,
                precision_rounding=move.product_uom.rounding,
            )
        )
        if not billable_moves:
            raise UserError(_('There are no billable spare parts.'))
        return repair.action_create_sale_order()

    def action_view_parts_repair(self):
        self.ensure_one()
        self._check_spare_parts_access()
        if not self.repair_order_id:
            raise UserError(_('No spare-parts repair order has been created yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Order'),
            'res_model': 'repair.order',
            'view_mode': 'form',
            'res_id': self.repair_order_id.id,
        }

    def action_view_parts_quotation(self):
        self.ensure_one()
        self._check_spare_parts_access()
        if not self.parts_sale_order_id:
            raise UserError(_('No spare-parts quotation has been created yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Parts Quotation'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.parts_sale_order_id.id,
        }

    def _sync_rental_reference_vals(self, vals):
        line_id = vals.get('rental_order_line_id')
        order_id = vals.get('rental_order_id')

        if line_id:
            line = self.env['sale.order.line'].browse(line_id).exists()
            if line:
                vals.setdefault('rental_order_id', line.order_id.id)
                vals.setdefault('rental_customer_id', line.order_id.partner_id.id)
                vals.setdefault('rental_product_id', line.product_id.id)
            return vals

        if order_id:
            order = self.env['sale.order'].browse(order_id).exists()
            if order:
                vals.setdefault('rental_customer_id', order.partner_id.id)
                current_line_id = vals.get('rental_order_line_id')
                if current_line_id:
                    current_line = self.env['sale.order.line'].browse(current_line_id).exists()
                    if current_line and current_line.order_id != order:
                        vals['rental_order_line_id'] = False
                if vals.get('rental_order_line_id') is False:
                    vals.setdefault('rental_product_id', False)
        return vals

    @api.onchange('rental_customer_id')
    def _onchange_rental_customer_id(self):
        domain = [('order_type', '=', 'rental')]
        if self.rental_customer_id:
            domain.append(('partner_id', 'child_of', self.rental_customer_id.commercial_partner_id.id))
            if self.rental_order_id and self.rental_order_id.partner_id.commercial_partner_id != self.rental_customer_id.commercial_partner_id:
                self.rental_order_id = False
                self.rental_order_line_id = False
                self.rental_product_id = False
        return {'domain': {'rental_order_id': domain}}

    @api.onchange('rental_order_id')
    def _onchange_rental_order_id(self):
        if not self.rental_order_id:
            self.rental_order_line_id = False
            return {'domain': {'rental_order_line_id': [('id', '=', False)]}}

        self.rental_customer_id = self.rental_order_id.partner_id
        order_lines = self.rental_order_id.order_line.filtered(lambda line: line.product_id)
        if self.rental_order_line_id and self.rental_order_line_id.order_id != self.rental_order_id:
            self.rental_order_line_id = False
        if not self.rental_order_line_id and len(order_lines) == 1:
            self.rental_order_line_id = order_lines
        return {'domain': {'rental_order_line_id': [('order_id', '=', self.rental_order_id.id)]}}

    @api.onchange('rental_order_line_id')
    def _onchange_rental_order_line_id(self):
        if self.rental_order_line_id:
            self.rental_order_id = self.rental_order_line_id.order_id
            self.rental_customer_id = self.rental_order_line_id.order_id.partner_id
            self.rental_product_id = self.rental_order_line_id.product_id

    def init(self):
        self.env.cr.execute(
            """
            UPDATE maintenance_request mr
               SET rental_order_id = sol.order_id,
                   rental_customer_id = so.partner_id,
                   rental_product_id = COALESCE(mr.rental_product_id, sol.product_id)
              FROM sale_order_line sol
              JOIN sale_order so ON so.id = sol.order_id
             WHERE mr.rental_order_line_id = sol.id
               AND so.order_type = 'rental'
               AND (
                    mr.rental_order_id IS NULL
                    OR mr.rental_customer_id IS NULL
                    OR mr.rental_product_id IS NULL
               )
            """
        )
        self.env.cr.execute(
            """
            UPDATE maintenance_request mr
               SET rental_customer_id = so.partner_id
              FROM sale_order so
             WHERE mr.rental_order_id = so.id
               AND so.order_type = 'rental'
               AND mr.rental_customer_id IS NULL
            """
        )

    def action_open_accept_sign_wizard(self, target_stage_id=False):
        self.ensure_one()
        target_stage = self.env['maintenance.stage'].browse(target_stage_id).exists() if target_stage_id else False
        return {
            'name': _('Accept & Sign'),
            'type': 'ir.actions.act_window',
            'res_model': 'rental.maintenance.accept.sign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_target_stage_id': target_stage.id if target_stage else False,
                'default_customer_name': self.rental_order_id.partner_id.name if self.rental_order_id else '',
            },
        }

    @api.depends('schedule_date', 'duration')
    def _compute_end_datetime(self):
        for rec in self:
            rec.maintenance_end_datetime = (
                rec.schedule_date + timedelta(hours=rec.duration)
                if rec.schedule_date and rec.duration
                else False
            )

    maintenance_end_datetime = fields.Datetime(
        string="End Time",
        compute="_compute_end_datetime",
        store=True
    )

    @api.depends('rental_product_id', 'equipment_id', 'schedule_date', 'duration')
    def _compute_display_name(self):
        for rental in self:
            name = "[{}] {} - {} > {}".format(
                rental.name,
                rental.rental_product_id.display_name if rental.rental_product_id else rental.equipment_id.name,
                rental.schedule_date,
                rental.maintenance_end_datetime,
            )
            rental.display_name = name

    @api.constrains('rental_product_id', 'schedule_date', 'duration')
    def _check_active_maintenance_conflict(self):
        """Prevent selecting a product already under maintenance during the same period."""
        for rec in self:
            if not rec.rental_product_id or not rec.schedule_date:
                continue

            # compute this request’s end time
            end_time = rec.schedule_date + timedelta(hours=rec.duration or 0)

            # find overlapping maintenance for same product
            conflicts = self.search([
                ('id', '!=', rec.id),
                ('rental_product_id', '=', rec.rental_product_id.id),
                ('stage_id.done', '=', False),  # exclude completed ones
                ('schedule_date', '<=', end_time),
                ('maintenance_end_datetime', '>=', rec.schedule_date),
            ])
            conflict = conflicts.filtered(
                lambda request: not (
                    rec.rental_order_line_id
                    and rec.rental_unit_number
                    and request.rental_order_line_id == rec.rental_order_line_id
                    and request.rental_unit_number
                    and request.rental_unit_number != rec.rental_unit_number
                )
            )[:1]

            if conflict:
                raise ValidationError(
                    f"{rec.rental_product_id.display_name} is already scheduled for maintenance:\n"
                    f"- From: {conflict.schedule_date}\n"
                    f"- To: {conflict.maintenance_end_datetime}\n\n"
                    f"Please choose another time."
                )
