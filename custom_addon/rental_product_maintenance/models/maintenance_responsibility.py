from odoo import api, fields, models


class MaintenanceRequestResponsibility(models.Model):
    _inherit = 'maintenance.request'

    responsible_ids = fields.Many2many(
        'res.users',
        'maintenance_request_responsible_rel',
        'request_id',
        'user_id',
        string='Responsible',
        domain=[('share', '=', False)],
        help='Users responsible for handling this maintenance request.',
    )

    def init(self):
        """Keep the original responsible user visible after enabling multi-user responsibility."""
        super().init()
        self.env.cr.execute(
            """
            INSERT INTO maintenance_request_responsible_rel (request_id, user_id)
            SELECT mr.id, mr.user_id
              FROM maintenance_request mr
             WHERE mr.user_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1
                     FROM maintenance_request_responsible_rel rel
                    WHERE rel.request_id = mr.id AND rel.user_id = mr.user_id
               )
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        # Keep legacy integrations (which use user_id as the primary owner) working.
        for request in requests:
            if not request.responsible_ids and request.user_id:
                request.responsible_ids = [(4, request.user_id.id)]
        return requests

    def write(self, vals):
        result = super().write(vals)
        if 'responsible_ids' in vals:
            for request in self:
                request.user_id = request.responsible_ids[:1].id or False
        return result
