# -*- coding: utf-8 -*-
# Copyright 2025 Lucky Kurniawan <kurniawanluckyy@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': 'Product Rental Maintenance',
    'summary': '',
    'version': '18.0.2.0.0',
    'author': 'Lucky Kurniawan',
    'website': 'https://github.com/kurniawanlucky/odoo_addons',
    'category': 'Product Management',
    'depends': ['rental_product_base', 'maintenance', 'repair', 'stock_account'],
    'data': [
        'security/maintenance_spare_parts_security.xml',
        'security/ir.model.access.csv',
        'data/spare_parts_data.xml',
        'wizards/maintenance_accept_sign_wizard_views.xml',
        'views/maintenance_request_views.xml',
        'views/product_template_views.xml',
        'report/maintenance_spare_parts_templates.xml',
        'report/maintenance_spare_parts_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rental_product_maintenance/static/src/js/maintenance_statusbar_signature.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
}
