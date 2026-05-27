from datetime import timedelta

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _archive_open_rental_maintenance_requests(self):
        MaintenanceRequest = self.env['maintenance.request'].sudo()
        for order in self.filtered(lambda so: so.order_type == 'rental'):
            requests = MaintenanceRequest.search([
                ('archive', '=', False),
                ('stage_id.done', '=', False),
                '|',
                ('rental_order_id', '=', order.id),
                ('rental_order_line_id', 'in', order.order_line.ids),
            ])
            if requests:
                requests.write({'archive': True})
                for request in requests:
                    request.message_post(
                        body=_("Archived because rental order %s was returned.") % order.display_name
                    )

    def _create_rental_preventive_maintenance_requests(self):
        MaintenanceRequest = self.env['maintenance.request']
        for order in self.filtered(lambda so: so.order_type == 'rental'):
            for line in order.order_line.filtered(
                lambda sol: (
                    sol.product_id
                    and sol.product_id.product_tmpl_id.rental_preventive_maintenance
                    and sol.product_id.product_tmpl_id.rental_preventive_maintenance_days
                    and sol.rental_start_datetime
                    and sol.rental_end_datetime
                )
            ):
                product = line.product_id
                maintenance_days = product.product_tmpl_id.rental_preventive_maintenance_days
                schedule_date = line.rental_start_datetime + timedelta(days=maintenance_days)
                while schedule_date <= line.rental_end_datetime:
                    existing_request = MaintenanceRequest.search([
                        ('rental_order_line_id', '=', line.id),
                        ('rental_product_id', '=', product.id),
                        ('schedule_date', '=', schedule_date),
                    ], limit=1)
                    if not existing_request:
                        MaintenanceRequest.create({
                            'name': _('Preventive Maintenance - %s') % product.display_name,
                            'rental_product_id': product.id,
                            'rental_order_id': order.id,
                            'rental_order_line_id': line.id,
                            'maintenance_type': 'preventive',
                            'schedule_date': schedule_date,
                            'duration': 1.0,
                            'description': _(
                                'Auto-created for rental order %(order)s. '
                                'Preventive maintenance interval: every %(days)s day(s) until %(end)s.'
                            ) % {
                                'order': order.name,
                                'days': maintenance_days,
                                'end': line.rental_end_datetime,
                            },
                            'company_id': order.company_id.id,
                        })
                    schedule_date += timedelta(days=maintenance_days)

    def action_confirm(self):
        action = super().action_confirm()
        self._create_rental_preventive_maintenance_requests()
        return action

    def action_rental_return(self):
        action = super().action_rental_return()
        self._archive_open_rental_maintenance_requests()
        return action
