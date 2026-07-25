from pathlib import Path
from xml.etree import ElementTree


ADDON_PATH = Path(__file__).resolve().parents[1]


def test_purchase_delivery_status_view_updates_receipt_status_badges():
    view_path = ADDON_PATH / "views" / "purchase_order_views.xml"
    tree = ElementTree.parse(view_path)
    root = tree.getroot()

    receipt_fields = [
        field
        for field in root.iter("field")
        if field.attrib.get("name") == "receipt_status"
        and field.attrib.get("position") != "replace"
    ]

    assert len(receipt_fields) == 4
    assert all(field.attrib.get("string") == "Delivery Status" for field in receipt_fields)
    assert all(field.attrib.get("widget") == "badge" for field in receipt_fields)
    assert all("optional" not in field.attrib for field in receipt_fields)
    assert all("decoration-success" in field.attrib for field in receipt_fields)
    assert all("decoration-warning" in field.attrib for field in receipt_fields)
    assert all("decoration-muted" in field.attrib for field in receipt_fields)
