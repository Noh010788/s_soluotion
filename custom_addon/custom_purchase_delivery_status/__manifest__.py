{
    'name': 'Purchase Delivery Status',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Show Delivery Status in Purchase Order views',
    'depends': ['purchase_stock'],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
