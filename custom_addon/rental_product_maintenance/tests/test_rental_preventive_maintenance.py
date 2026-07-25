from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestRentalPreventiveMaintenance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Rental Maintenance Customer',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Rental Product With Preventive Maintenance',
            'is_rental': True,
            'rental_preventive_maintenance': True,
            'rental_preventive_maintenance_days': 1,
            'type': 'service',
            'list_price': 100.0,
        })

    def _create_rental_order(self, quantity):
        start = fields.Datetime.now()
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_type': 'rental',
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': quantity,
                'price_unit': 100.0,
                'rental_type': 'day',
                'rental_qty': 3.0,
                'rental_start_datetime': start,
                'rental_end_datetime': start + timedelta(days=3),
            })],
        })

    def test_creates_preventive_maintenance_per_rented_unit(self):
        order = self._create_rental_order(2)

        order._create_rental_preventive_maintenance_requests()

        requests = self.env['maintenance.request'].search([
            ('rental_order_id', '=', order.id),
            ('rental_order_line_id', '=', order.order_line.id),
            ('rental_product_id', '=', self.product.id),
        ])
        self.assertEqual(len(requests), 6)
        self.assertEqual(
            sorted(requests.mapped('rental_unit_number')),
            [1, 1, 1, 2, 2, 2],
        )

    def test_creates_preventive_maintenance_when_dates_are_added_after_confirm(self):
        order = self._create_rental_order(2)
        line = order.order_line
        line.write({
            'rental_start_datetime': False,
            'rental_end_datetime': False,
        })
        order.action_confirm()
        self.assertFalse(self.env['maintenance.request'].search([
            ('rental_order_id', '=', order.id),
        ]))

        start = fields.Datetime.now()
        line.write({
            'rental_start_datetime': start,
            'rental_end_datetime': start + timedelta(days=3),
        })

        requests = self.env['maintenance.request'].search([
            ('rental_order_id', '=', order.id),
            ('rental_order_line_id', '=', line.id),
            ('rental_product_id', '=', self.product.id),
        ])
        self.assertEqual(len(requests), 6)
        self.assertEqual(
            sorted(requests.mapped('rental_unit_number')),
            [1, 1, 1, 2, 2, 2],
        )
