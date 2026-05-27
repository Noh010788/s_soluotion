from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rental_preventive_maintenance = fields.Boolean(
        string="Preventive Maintenance",
        help="Create preventive maintenance requests while this product is rented.",
    )
    rental_preventive_maintenance_days = fields.Float(
        string="Preventive Maintenance Days",
        help="Interval in days between preventive maintenance requests during a rental.",
    )

    def action_view_maintenance(self):
        self.ensure_one()
        action = self.env.ref('maintenance.hr_equipment_request_action').read()[0]
        action['domain'] = [('rental_product_id', 'in', self.product_variant_ids.ids)]
        return action
