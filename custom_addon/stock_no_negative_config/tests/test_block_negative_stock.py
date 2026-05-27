from odoo.addons.stock.tests.common import TestStockCommon
from odoo.exceptions import UserError


class TestBlockNegativeStock(TestStockCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.block_negative_stock = True
        cls.product = cls.env['product.product'].create({
            'name': 'No Negative Product',
            'is_storable': True,
        })
        cls.stock_location_record = cls.env.ref('stock.stock_location_stock')
        cls.customer_location_record = cls.env.ref('stock.stock_location_customers')

    def _create_done_move(self, quantity):
        move = self.env['stock.move'].create({
            'name': 'No negative test move',
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': quantity,
            'location_id': self.stock_location_record.id,
            'location_dest_id': self.customer_location_record.id,
        })
        move._action_confirm()
        move.quantity = quantity
        move.picked = True
        return move

    def test_blocks_outgoing_move_that_would_make_stock_negative(self):
        self.env['stock.quant']._update_available_quantity(
            self.product,
            self.stock_location_record,
            2,
        )
        move = self._create_done_move(3)

        with self.assertRaises(UserError):
            move._action_done()

    def test_allows_outgoing_move_when_stock_is_sufficient(self):
        self.env['stock.quant']._update_available_quantity(
            self.product,
            self.stock_location_record,
            3,
        )
        move = self._create_done_move(3)

        move._action_done()

        self.assertEqual(move.state, 'done')
