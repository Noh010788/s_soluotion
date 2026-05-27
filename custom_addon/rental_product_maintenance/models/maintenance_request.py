from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_rental_reference_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._sync_rental_reference_vals(vals)
        if 'stage_id' in vals and not self.env.context.get('skip_maintenance_customer_signature'):
            done_stage = self.env['maintenance.stage'].browse(vals['stage_id'])
            if done_stage.done:
                unsigned_requests = self.filtered(lambda request: not request.customer_accepted or not request.customer_signature)
                if unsigned_requests:
                    raise UserError(_("Customer must accept and sign before this maintenance request can be marked Done."))
        return super().write(vals)

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
            conflict = self.search([
                ('id', '!=', rec.id),
                ('rental_product_id', '=', rec.rental_product_id.id),
                ('stage_id.done', '=', False),  # exclude completed ones
                ('schedule_date', '<=', end_time),
                ('maintenance_end_datetime', '>=', rec.schedule_date),
            ], limit=1)

            if conflict:
                raise ValidationError(
                    f"{rec.rental_product_id.display_name} is already scheduled for maintenance:\n"
                    f"- From: {conflict.schedule_date}\n"
                    f"- To: {conflict.maintenance_end_datetime}\n\n"
                    f"Please choose another time."
                )
