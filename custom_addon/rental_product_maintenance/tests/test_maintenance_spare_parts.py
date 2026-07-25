from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestMaintenanceSpareParts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Maintenance Spare Parts Customer',
            'customer_rank': 1,
        })
        cls.category = cls.env.ref(
            'rental_product_maintenance.product_category_spare_parts_mechanical'
        )
        cls.source_location = cls.env.ref(
            'rental_product_maintenance.stock_location_spare_parts'
        )
        cls.consumption_location = cls.env.ref(
            'rental_product_maintenance.stock_location_maintenance_consumption'
        )
        cls.product = cls.env['product.product'].create({
            'name': 'Test Maintenance Bearing',
            'default_code': 'TEST-SP-001',
            'categ_id': cls.category.id,
            'type': 'consu',
            'is_storable': True,
            'is_rental': False,
            'standard_price': 100.0,
            'list_price': 150.0,
        })

    def _set_stock(self, product, quantity):
        quant = self.env['stock.quant'].create({
            'product_id': product.id,
            'location_id': self.source_location.id,
            'inventory_quantity': quantity,
        })
        quant.action_apply_inventory()

    def _create_request(self, planned_qty=5.0, billable=True):
        request = self.env['maintenance.request'].create({
            'name': 'Maintenance With Spare Parts',
            'rental_customer_id': self.partner.id,
            'company_id': self.company.id,
        })
        move = self.env['stock.move'].create({
            'maintenance_request_id': request.id,
            'product_id': self.product.id,
            'product_uom_qty': planned_qty,
            'product_uom': self.product.uom_id.id,
            'maintenance_billable': billable,
        })
        return request, move

    def test_reserve_issue_and_consume_actual_quantity(self):
        self._set_stock(self.product, 10.0)
        request, move = self._create_request(planned_qty=5.0)

        request.action_reserve_spare_parts()
        self.assertEqual(request.parts_state, 'confirmed')
        self.assertEqual(move.state, 'assigned')
        self.assertEqual(move.quantity, 5.0)

        request.action_issue_spare_parts()
        self.assertEqual(request.parts_state, 'under_repair')

        move.quantity = 3.0
        request.action_consume_spare_parts()

        self.assertEqual(request.parts_state, 'done')
        self.assertEqual(move.state, 'done')
        self.assertEqual(move.quantity, 3.0)
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.product, self.source_location
            ),
            7.0,
        )
        self.assertEqual(move.location_dest_id, self.consumption_location)
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.product, self.consumption_location
            ),
            3.0,
        )
        self.assertTrue(move.stock_valuation_layer_ids)
        self.assertGreater(request.spare_parts_cost, 0.0)

    def test_return_unreserves_without_consuming_stock(self):
        self._set_stock(self.product, 5.0)
        request, move = self._create_request(planned_qty=4.0)

        request.action_reserve_spare_parts()
        request.action_return_spare_parts()

        self.assertEqual(request.parts_state, 'cancel')
        self.assertEqual(move.state, 'cancel')
        self.assertEqual(move.quantity, 0.0)
        self.assertEqual(request.spare_parts_cost, 0.0)
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.product, self.source_location
            ),
            5.0,
        )

        done_stage = self.env['maintenance.stage'].search([
            ('done', '=', True),
        ], limit=1) or self.env['maintenance.stage'].create({
            'name': 'Done After Returned Parts',
            'done': True,
        })
        request.with_context(
            skip_maintenance_customer_signature=True
        ).write({'stage_id': done_stage.id})
        self.assertEqual(request.stage_id, done_stage)

    def test_reserved_part_cannot_be_deleted(self):
        self._set_stock(self.product, 2.0)
        request, move = self._create_request(planned_qty=1.0)
        request.action_reserve_spare_parts()

        with self.assertRaisesRegex(ValidationError, 'Return or consume'):
            move.unlink()

    def test_non_storable_product_is_rejected(self):
        service_part = self.env['product.product'].create({
            'name': 'Test Non Storable Spare Part',
            'categ_id': self.category.id,
            'type': 'consu',
            'is_storable': False,
        })
        request = self.env['maintenance.request'].create({
            'name': 'Maintenance With Invalid Spare Part',
            'rental_customer_id': self.partner.id,
            'company_id': self.company.id,
        })

        with self.assertRaisesRegex(ValidationError, 'must be a storable product'):
            self.env['stock.move'].create({
                'maintenance_request_id': request.id,
                'product_id': service_part.id,
                'product_uom_qty': 1.0,
                'product_uom': service_part.uom_id.id,
            })

    def test_insufficient_spare_parts_are_blocked(self):
        self._set_stock(self.product, 1.0)
        request, _move = self._create_request(planned_qty=2.0)

        with self.assertRaisesRegex(UserError, 'Not enough stock'):
            request.action_reserve_spare_parts()

    def test_customer_quotation_uses_actual_billable_quantity(self):
        self._set_stock(self.product, 10.0)
        request, move = self._create_request(planned_qty=5.0)
        request.action_reserve_spare_parts()
        request.action_issue_spare_parts()
        move.quantity = 2.0
        request.action_consume_spare_parts()

        request.action_create_spare_parts_quotation()

        quotation = request.parts_sale_order_id
        self.assertTrue(quotation)
        self.assertEqual(len(quotation.order_line), 1)
        self.assertEqual(quotation.order_line.product_id, self.product)
        self.assertEqual(quotation.order_line.product_uom_qty, 2.0)
        self.assertEqual(quotation.order_line.price_unit, 150.0)

    def test_zero_used_quantity_does_not_create_quotation(self):
        self._set_stock(self.product, 2.0)
        request, move = self._create_request(planned_qty=1.0)
        request.action_reserve_spare_parts()
        request.action_issue_spare_parts()
        move.quantity = 0.0
        request.action_consume_spare_parts()

        self.assertEqual(move.state, 'cancel')
        self.assertEqual(request.spare_parts_cost, 0.0)
        with self.assertRaisesRegex(UserError, 'no billable spare parts'):
            request.action_create_spare_parts_quotation()

    def test_non_billable_part_is_not_added_to_quotation(self):
        second_product = self.env['product.product'].create({
            'name': 'Test Internal Fuse',
            'default_code': 'TEST-SP-002',
            'categ_id': self.category.id,
            'type': 'consu',
            'is_storable': True,
            'is_rental': False,
            'standard_price': 50.0,
            'list_price': 75.0,
        })
        self._set_stock(self.product, 2.0)
        self._set_stock(second_product, 2.0)
        request, billable_move = self._create_request(planned_qty=1.0)
        non_billable_move = self.env['stock.move'].create({
            'maintenance_request_id': request.id,
            'product_id': second_product.id,
            'product_uom_qty': 1.0,
            'product_uom': second_product.uom_id.id,
            'maintenance_billable': False,
        })
        request.action_reserve_spare_parts()
        request.action_issue_spare_parts()
        billable_move.quantity = 1.0
        non_billable_move.quantity = 1.0
        request.action_consume_spare_parts()

        request.action_create_spare_parts_quotation()

        self.assertEqual(request.parts_sale_order_id.order_line.product_id, self.product)

    def test_done_stage_requires_completed_spare_parts(self):
        request, _move = self._create_request(planned_qty=1.0)
        done_stage = self.env['maintenance.stage'].search([
            ('done', '=', True),
        ], limit=1)
        if not done_stage:
            done_stage = self.env['maintenance.stage'].create({
                'name': 'Done for Spare Parts Test',
                'done': True,
            })

        with self.assertRaisesRegex(UserError, 'Consume or return'):
            request.with_context(
                skip_maintenance_customer_signature=True
            ).write({'stage_id': done_stage.id})
