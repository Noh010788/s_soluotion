from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    warranty_period_months = fields.Integer(string='Warranty Period (Months)', default=12)
    warranty_type = fields.Selection([
        ('repair', 'Free Repair'), ('replace', 'Parts Replacement'),
        ('parts_only', 'Parts Only (Labor Excluded)'),
    ], string='Warranty Type', default='repair')
    warranty_terms = fields.Text(string='Warranty Terms')


class StockLot(models.Model):
    _inherit = 'stock.lot'

    warranty_start_date = fields.Date(string='Warranty Start')
    warranty_expiry_date = fields.Date(string='Warranty Expiry')
    warranty_active = fields.Boolean(compute='_compute_warranty_active', string='Warranty Active')

    @api.depends('warranty_expiry_date')
    def _compute_warranty_active(self):
        today = date.today()
        for lot in self:
            lot.warranty_active = bool(lot.warranty_expiry_date and lot.warranty_expiry_date >= today)


class WarrantyClaim(models.Model):
    _name = 'warranty.claim'
    _description = 'Warranty Claim'
    _order = 'claim_date desc, id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    customer_id = fields.Many2one('res.partner', required=True)
    product_id = fields.Many2one('product.product', required=True)
    lot_id = fields.Many2one('stock.lot', string='Serial Number', domain="[('product_id', '=', product_id)]")
    invoice_id = fields.Many2one('account.move', domain="[('move_type', 'in', ('out_invoice', 'out_refund'))]")
    picking_id = fields.Many2one('stock.picking')
    claim_date = fields.Date(default=fields.Date.context_today, required=True)
    issue = fields.Text(string='Issue / Problem', required=True)
    warranty_start_date = fields.Date(related='lot_id.warranty_start_date', readonly=True)
    warranty_expiry_date = fields.Date(related='lot_id.warranty_expiry_date', readonly=True)
    in_warranty = fields.Boolean(compute='_compute_in_warranty', string='Within Warranty')
    state = fields.Selection([
        ('new', 'New'), ('repair', 'In Repair'), ('done', 'Done'), ('rejected', 'Rejected'),
    ], default='new', required=True)
    parts_cost = fields.Monetary(string='Parts Cost')
    labor_cost = fields.Monetary(string='Labor Cost')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    warranty_terms = fields.Text(related='product_id.product_tmpl_id.warranty_terms', readonly=True)

    @api.depends('warranty_expiry_date', 'claim_date')
    def _compute_in_warranty(self):
        for claim in self:
            claim.in_warranty = bool(claim.warranty_expiry_date and claim.warranty_expiry_date >= (claim.claim_date or date.today()))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('warranty.claim') or 'New'
        return super().create(vals_list)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        result = super().button_validate()
        for picking in self:
            if picking.state == 'done':
                start = fields.Date.to_date(picking.date_done or fields.Datetime.now())
                for line in picking.move_line_ids.filtered(lambda l: l.lot_id and l.product_id.product_tmpl_id.warranty_period_months):
                    months = line.product_id.product_tmpl_id.warranty_period_months
                    line.lot_id.write({'warranty_start_date': start, 'warranty_expiry_date': start + relativedelta(months=months)})
        return result
