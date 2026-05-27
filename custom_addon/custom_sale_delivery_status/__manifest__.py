{
    'name': 'Sale Delivery Status',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Show Delivery Status in Sales Order List View',
    'depends': ['sale_stock'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
