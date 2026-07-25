from odoo import api, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.model
    def _configure_maintenance_spare_parts_accounting(self):
        """Configure the module categories safely for every active company.

        Product category accounting fields are company dependent.  The XML
        creates the categories with manual valuation first so installing the
        module also works on databases without a configured chart of accounts.
        We then copy the company's existing stock accounts and enable AVCO /
        automated valuation only when every required account and journal is
        available.
        """
        category_xmlids = (
            'rental_product_maintenance.product_category_spare_parts',
            'rental_product_maintenance.product_category_spare_parts_mechanical',
            'rental_product_maintenance.product_category_spare_parts_electrical',
            'rental_product_maintenance.product_category_spare_parts_consumables',
        )
        categories = self.browse()
        for xmlid in category_xmlids:
            category = self.env.ref(xmlid, raise_if_not_found=False)
            if category:
                categories |= category

        source_category = self.env.ref(
            'product.product_category_all', raise_if_not_found=False
        )
        if not categories or not source_category:
            return True

        account_fields = (
            'property_stock_account_input_categ_id',
            'property_stock_account_output_categ_id',
            'property_stock_valuation_account_id',
            'property_stock_journal',
            'property_account_expense_categ_id',
            'property_account_income_categ_id',
        )
        mandatory_fields = (
            'property_stock_account_input_categ_id',
            'property_stock_account_output_categ_id',
            'property_stock_valuation_account_id',
            'property_stock_journal',
        )

        for company in self.env['res.company'].search([('active', '=', True)]):
            source = source_category.with_company(company)
            source_values = {
                field_name: source[field_name]
                for field_name in account_fields
            }
            for category in categories.with_company(company):
                values = {'property_cost_method': 'average'}
                for field_name, value in source_values.items():
                    if value and not category[field_name]:
                        values[field_name] = value.id
                category.write(values)
                if all(category[field_name] for field_name in mandatory_fields):
                    category.property_valuation = 'real_time'

        consumption_location = self.env.ref(
            'rental_product_maintenance.stock_location_maintenance_consumption',
            raise_if_not_found=False,
        )
        if consumption_location and consumption_location.company_id:
            source = source_category.with_company(consumption_location.company_id)
            expense_account = source.property_account_expense_categ_id
            if expense_account:
                consumption_location.write({
                    'valuation_in_account_id': expense_account.id,
                    'valuation_out_account_id': expense_account.id,
                })
        return True
