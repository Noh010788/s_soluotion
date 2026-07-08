from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "sale_discount_total")
class TestSaleDiscountAmount(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Discount Test Customer"})
        self.product = self.env["product.product"].create({
            "name": "Discount Test Product",
            "type": "consu",
            "list_price": 100000.0,
        })

    def _create_order(self, line_values):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                (0, 0, {
                    "product_id": self.product.id,
                    "product_uom_qty": qty,
                    "price_unit": price,
                })
                for qty, price in line_values
            ],
        })

    def test_line_discount_amount_is_computed_from_discount_percent(self):
        order = self._create_order([(2.0, 100000.0)])
        line = order.order_line
        line.discount = 10.0

        self.assertAlmostEqual(line.total_discount, 20000.0, places=2)
        self.assertAlmostEqual(order.amount_discount, 20000.0, places=2)

    def test_fixed_order_discount_updates_each_line_discount_amount(self):
        order = self._create_order([(1.0, 100000.0), (1.0, 300000.0)])
        order.discount_type = "amount"
        order.discount_rate = 40000.0
        order.supply_rate()

        discounts = order.order_line.mapped("total_discount")
        self.assertAlmostEqual(discounts[0], 10000.0, places=2)
        self.assertAlmostEqual(discounts[1], 30000.0, places=2)
        self.assertAlmostEqual(sum(discounts), 40000.0, places=2)

    def test_manual_line_discount_amount_updates_discount_percent(self):
        order = self._create_order([(1.0, 100000.0)])
        line = order.order_line

        line.total_discount = 15000.0

        self.assertAlmostEqual(line.discount, 15.0, places=2)
        self.assertAlmostEqual(line.total_discount, 15000.0, places=2)
        self.assertAlmostEqual(order.amount_discount, 15000.0, places=2)

    def test_zero_global_discount_does_not_override_manual_line_discount(self):
        order = self._create_order([(1.0, 100000.0)])
        order.discount_type = "amount"
        order.discount_rate = 0.0
        order.order_line.discount = 12.5

        order.supply_rate()

        self.assertAlmostEqual(order.order_line.discount, 12.5, places=2)
        self.assertAlmostEqual(order.order_line.total_discount, 12500.0, places=2)
