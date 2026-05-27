from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    block_negative_stock = fields.Boolean(
        string='Block Negative Stock',
        help='Prevent validating stock operations that would make internal or transit stock negative.',
    )

