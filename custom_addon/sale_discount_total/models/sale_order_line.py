# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Sreerag PM(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    """This class inherits "sale.order.line" and adds fields discount,
     total_discount """
    _inherit = "sale.order.line"

    discount = fields.Float(string='Discount (%)', digits=(16, 20), default=0.0,
                            help="Discount needed.")
    total_discount = fields.Monetary(
        string="Disc. AMT",
        compute="_compute_total_discount",
        inverse="_inverse_total_discount",
        currency_field="currency_id",
        store=True,
        help="Discount amount for this order line.",
    )

    @api.depends("product_uom_qty", "price_unit", "discount")
    def _compute_total_discount(self):
        for line in self:
            line.total_discount = (
                line.product_uom_qty * line.price_unit * line.discount
            ) / 100.0

    def _inverse_total_discount(self):
        for line in self:
            base_amount = line.product_uom_qty * line.price_unit
            line.discount = (
                (line.total_discount / base_amount) * 100.0
                if base_amount
                else 0.0
            )
