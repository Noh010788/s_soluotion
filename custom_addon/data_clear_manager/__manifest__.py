{
    "name": "Data Clear Manager",
    "summary": "Clear transaction data by application area",
    "version": "18.0.1.0.0",
    "category": "Administration",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": [
        "sale_management",
        "purchase",
        "stock",
        "account",
        "maintenance",
        "rental_product_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/data_clear_manager_views.xml",
    ],
    "installable": True,
    "application": False,
}
