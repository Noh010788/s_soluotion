from odoo import _, fields, models
from odoo.exceptions import UserError


class MaintenanceAcceptSignWizard(models.TransientModel):
    _name = 'rental.maintenance.accept.sign.wizard'
    _description = 'Maintenance Customer Accept and Sign'

    request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        required=True,
        readonly=True,
    )
    target_stage_id = fields.Many2one(
        'maintenance.stage',
        string='Done Stage',
        readonly=True,
    )
    customer_name = fields.Char(
        string='Customer Name',
        required=True,
    )
    signature = fields.Image(
        string='Signature',
        required=True,
        max_width=1024,
        max_height=512,
    )

    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        request = self.env['maintenance.request'].browse(vals.get('request_id')).exists()
        if request and 'customer_name' in fields_list and not vals.get('customer_name'):
            vals['customer_name'] = request.rental_order_id.partner_id.name or request.owner_user_id.name or ''
        return vals

    def action_accept_and_done(self):
        self.ensure_one()
        done_stage = self.target_stage_id
        if done_stage and not done_stage.done:
            raise UserError(_("The selected target stage is not a Done stage."))
        if not done_stage:
            done_stage = self.env['maintenance.stage'].search([('done', '=', True)], order='sequence, id', limit=1)
        if not done_stage:
            raise UserError(_("Please configure a Done stage for Maintenance first."))

        self.request_id.write({
            'customer_accepted': True,
            'customer_signature': self.signature,
            'customer_signed_by': self.customer_name,
            'customer_signed_on': fields.Datetime.now(),
        })
        self.request_id.with_context(skip_maintenance_customer_signature=True).write({
            'stage_id': done_stage.id,
        })
        return {'type': 'ir.actions.act_window_close'}
