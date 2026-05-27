from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    block_negative_stock = fields.Boolean(
        related='company_id.block_negative_stock',
        readonly=False,
    )

