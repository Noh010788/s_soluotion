# -*- coding: utf-8 -*-
{
    "name": "SS Sale Quotation Report",
    "version": "18.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Custom quotation print layout for Sale orders",
    "author": "S Solution",
    "license": "LGPL-3",
    "depends": ["sale", "stock"],
    "data": [
        "report/sale_quotation_report.xml",
        "report/delivery_slip_report.xml",
        "report/invoice_report.xml",
    ],
    "installable": True,
    "application": False,
}
