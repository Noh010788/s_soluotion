from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def do_print_picking(self):
        self.write({"printed": True})
        return self.env.ref("stock.action_report_delivery").report_action(self)
