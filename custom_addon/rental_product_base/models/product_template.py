from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_rental = fields.Boolean(string="Rental", default=True)
    rental_price_per_hour = fields.Float(string="Rental Price / Hour", default=1.0, digits='Product Price')
    rental_price_per_week = fields.Float(string="Rental Price / Week", default=1.0, digits='Product Price')
    rental_price_per_month = fields.Float(string="Rental Price / Month", default=1.0, digits='Product Price')
    rental_price_per_day = fields.Float(string="Rental Price / Day", default=1.0, digits='Product Price')

    rental_min_hours = fields.Float(string="Minimum Hours", default=0)
    rental_min_days = fields.Float(string="Minimum Days", default=0)
    rental_min_weeks = fields.Float(string="Minimum Weeks", default=0)
    rental_min_months = fields.Float(string="Minimum Months", default=0)

    deposit_amount = fields.Float(string="Deposit")

    def init(self):
        self.env.cr.execute(
            """
            UPDATE product_template
               SET type = 'consu'
             WHERE type = 'rental'
            """
        )
