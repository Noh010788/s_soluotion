WEASYPRINT_REPORTS = frozenset(
    {
        "sale.report_saleorder",
        "stock.report_deliveryslip",
        "account.report_invoice_with_payments",
    }
)


def is_weasyprint_report(report_name):
    return report_name in WEASYPRINT_REPORTS


def build_page_css(
    page_format,
    orientation,
    margin_top,
    margin_right,
    margin_bottom,
    margin_left,
):
    return (
        f"@page {{ size: {page_format} {orientation.lower()}; "
        f"margin: {margin_top}mm {margin_right}mm "
        f"{margin_bottom}mm {margin_left}mm; }}"
    )
