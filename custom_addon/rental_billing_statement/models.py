from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_SNAPSHOT_TOKEN = object()


class Invoice(models.Model):
    _inherit = 'account.move'

    rental_billing_ids = fields.One2many('rental.billing.statement', 'invoice_id')

    def action_rental_billing(self):
        self.ensure_one()
        self._rental_billing_contract()
        return {'type': 'ir.actions.act_window', 'name': _('Rental Billing Statements'),
                'res_model': 'rental.billing.statement', 'view_mode': 'list,form',
                'domain': [('invoice_id', '=', self.id)],
                'context': {'default_invoice_id': self.id}}

    def _rental_billing_contract(self):
        self.ensure_one()
        if self.move_type != 'out_invoice' or self.state != 'posted':
            raise UserError(_('Select a posted customer invoice for the full rental contract.'))
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        periods = set()
        for line in lines:
            sale = line.sale_line_ids
            if len(sale) != 1 or sale.rental_type != 'month' or not sale.rental_start_datetime or sale.is_downpayment:
                raise UserError(_('Each invoice line must link to one monthly rental line. Mixed services and down payments are not supported.'))
            months = sale.rental_qty
            if months <= 0 or months != int(months):
                raise UserError(_('The rental duration must be a whole number of months.'))
            start = fields.Date.to_date(sale.rental_start_datetime)
            if fields.Date.to_date(sale.rental_end_datetime) != start + relativedelta(months=int(months)):
                raise UserError(_('Rental dates must match the number of months.'))
            periods.add((start, int(months)))
            if line.quantity != sale.product_uom_qty or line.currency_id.compare_amounts(line.price_subtotal, sale.price_subtotal):
                raise UserError(_('This invoice must cover the complete rental line, including its discount.'))
        if len(periods) != 1 or self.amount_total <= 0:
            raise UserError(_('All rental lines must share the same start date and duration, with a positive total.'))
        return periods.pop()

    def button_draft(self):
        if self.mapped('rental_billing_ids').filtered(lambda s: s.state == 'issued'):
            raise UserError(_('Cancel issued billing statements before resetting the invoice.'))
        return super().button_draft()


class Statement(models.Model):
    _name = 'rental.billing.statement'
    _description = 'Rental Billing Statement'
    _order = 'first_month, id'
    _check_company_auto = True

    name = fields.Char(default='New', readonly=True, copy=False)
    invoice_id = fields.Many2one('account.move', required=True, ondelete='restrict', check_company=True)
    company_id = fields.Many2one(related='invoice_id.company_id', store=True)
    partner_id = fields.Many2one(related='invoice_id.partner_id')
    currency_id = fields.Many2one(related='invoice_id.currency_id')
    first_month = fields.Integer(default=1, required=True, string='Starting installment')
    months = fields.Integer(default=1, required=True, string='Number of months')
    date = fields.Date(default=fields.Date.context_today, required=True, string='Billing date')
    due_date = fields.Date(required=True, default=fields.Date.context_today)
    period_start = fields.Date(readonly=True)
    period_end = fields.Date(readonly=True, string='Period end (inclusive)')
    amount_untaxed = fields.Monetary(readonly=True)
    amount_tax = fields.Monetary(readonly=True)
    amount_total = fields.Monetary(readonly=True)
    settled_amount = fields.Monetary(compute='_compute_settlement')
    amount_due = fields.Monetary(compute='_compute_settlement')
    settlement_status = fields.Selection([('unpaid', 'Unsettled'), ('partial', 'Partly settled'), ('paid', 'Settled')], compute='_compute_settlement')
    state = fields.Selection([('draft', 'Draft'), ('issued', 'Issued'), ('cancel', 'Cancelled')], default='draft', readonly=True, copy=False)
    line_ids = fields.One2many('rental.billing.statement.line', 'statement_id', readonly=True)

    @api.depends('invoice_id.amount_residual', 'invoice_id.amount_total', 'invoice_id.rental_billing_ids.state', 'state', 'first_month', 'amount_total')
    def _compute_settlement(self):
        for rec in self:
            # Allocate settlement chronologically, including credit notes/write-offs.
            available = max(0, rec.invoice_id.amount_total - rec.invoice_id.amount_residual)
            earlier = rec.invoice_id.rental_billing_ids.filtered(lambda x: x.state == 'issued' and (x.first_month, x.id) < (rec.first_month, rec.id))
            rec.settled_amount = min(rec.amount_total, max(0, available - sum(earlier.mapped('amount_total')))) if rec.state == 'issued' else 0
            rec.amount_due = rec.amount_total - rec.settled_amount
            rec.settlement_status = 'paid' if rec.amount_total and rec.currency_id.is_zero(rec.amount_due) else ('partial' if rec.settled_amount else 'unpaid')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft' or vals.get('line_ids'):
                raise UserError(_('Create a draft, then issue the statement.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals or 'line_ids' in vals or any(r.state != 'draft' for r in self):
            raise UserError(_('Issued statements are immutable. Use Cancel or Print again.'))
        return super().write(vals)

    def unlink(self):
        if any(r.state == 'issued' for r in self):
            raise UserError(_('Issued statements cannot be deleted. Cancel them first.'))
        return super().unlink()

    def action_issue(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only drafts can be issued.'))
        inv = self.invoice_id
        inv.check_access('read')
        # Serialize issuance per invoice, including concurrent requests.
        self.env.cr.execute('SELECT id FROM account_move WHERE id=%s FOR UPDATE', [inv.id])
        start, duration = inv._rental_billing_contract()
        end_month = self.first_month + self.months - 1
        if self.first_month < 1 or self.months < 1 or end_month > duration:
            raise ValidationError(_('Select installments within the contract (1 to %s).') % duration)
        if self.due_date < self.date:
            raise ValidationError(_('Due date cannot precede billing date.'))
        others = self.search([('invoice_id', '=', inv.id), ('state', '=', 'issued')])
        if any(self.first_month <= s.first_month + s.months - 1 and end_month >= s.first_month for s in others):
            raise ValidationError(_('These installments already have an issued statement. Reprint it or cancel it first.'))
        def portion(value):
            return inv.currency_id.round(value * end_month / duration) - inv.currency_id.round(value * (self.first_month - 1) / duration)
        vals = {'name': '%s / RB-%s' % (inv.name, self.id), 'state': 'issued',
                'period_start': start + relativedelta(months=self.first_month - 1),
                'period_end': start + relativedelta(months=end_month, days=-1),
                'amount_untaxed': portion(inv.amount_untaxed), 'amount_total': portion(inv.amount_total)}
        vals['amount_tax'] = vals['amount_total'] - vals['amount_untaxed']
        vals['line_ids'] = [(0, 0, {'name': l.name, 'quantity': l.quantity,
            'discount': l.discount, 'tax_names': ', '.join(l.tax_ids.mapped('name')),
            'subtotal': portion(l.price_subtotal)}) for l in inv.invoice_line_ids.filtered(lambda l: l.display_type == 'product')]
        super(Statement, self.with_context(billing_snapshot_token=_SNAPSHOT_TOKEN)).write(vals)
        return self.action_print()

    def action_cancel(self):
        for rec in self:
            self.env.cr.execute('SELECT id FROM account_move WHERE id=%s FOR UPDATE', [rec.invoice_id.id])
        return super().write({'state': 'cancel'})

    def action_print(self):
        if any(r.state != 'issued' for r in self):
            raise UserError(_('Issue the statement before printing.'))
        return self.env.ref('rental_billing_statement.report_action').report_action(self)


class StatementLine(models.Model):
    _name = 'rental.billing.statement.line'
    _description = 'Rental Billing Snapshot Line'
    statement_id = fields.Many2one('rental.billing.statement', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='statement_id.company_id', store=True)
    currency_id = fields.Many2one(related='statement_id.currency_id')
    name = fields.Text()
    quantity = fields.Float()
    discount = fields.Float()
    tax_names = fields.Char()
    subtotal = fields.Monetary()

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('billing_snapshot_token') is not _SNAPSHOT_TOKEN:
            raise UserError(_('Snapshot lines are created only when issuing a statement.'))
        return super().create(vals_list)


class Report(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, bodies, report_ref=False, **kwargs):
        report = self._get_report(report_ref) if report_ref else self
        if report.report_name == 'rental_billing_statement.document':
            return self._run_weasyprint(bodies, report, landscape=kwargs.get('landscape', False))
        return super()._run_wkhtmltopdf(bodies, report_ref=report_ref, **kwargs)
