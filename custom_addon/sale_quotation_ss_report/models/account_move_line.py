# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    invoice_description = fields.Char(
        string="Description",
        related="name",
        readonly=False,
    )
