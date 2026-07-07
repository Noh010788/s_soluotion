import hashlib
import unittest
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = MODULE_ROOT / "static" / "src" / "fonts"


class TestPhetsarathFontAssets(unittest.TestCase):
    def test_official_phetsarath_2_package_fonts_are_bundled(self):
        expected_hashes = {
            "Phetsarath_OT.ttf": (
                "561be504341623de95529024648fea725ea26cb8ff4cd4055725141f0020efd3"
            ),
            "Phetsarath_OT_Bold.ttf": (
                "36f21df96f12eefdb736eac979a3479900f1959d4ed55c5b82a7d72dd7829f9b"
            ),
        }

        actual_hashes = {
            name: hashlib.sha256((FONT_DIR / name).read_bytes()).hexdigest()
            for name in expected_hashes
        }

        self.assertEqual(actual_hashes, expected_hashes)

    def test_reports_use_the_phetsarath_ot_family(self):
        report_files = (
            "sale_quotation_report.xml",
            "delivery_slip_report.xml",
            "invoice_report.xml",
        )

        for filename in report_files:
            report_xml = (MODULE_ROOT / "report" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn('font-family: "Phetsarath OT"', report_xml)
            self.assertNotIn('font-family: "Phetsarath"', report_xml)

    def test_reports_do_not_force_grapheme_spacing(self):
        report_files = (
            "sale_quotation_report.xml",
            "delivery_slip_report.xml",
            "invoice_report.xml",
        )

        for filename in report_files:
            report_xml = (MODULE_ROOT / "report" / filename).read_text(
                encoding="utf-8"
            )
            self.assertNotIn("letter-spacing:", report_xml)

    def test_quotation_and_invoice_use_compact_product_rows(self):
        for filename in ("sale_quotation_report.xml", "invoice_report.xml"):
            report_xml = (MODULE_ROOT / "report" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn("height: 150px;", report_xml)
            self.assertIn("min-height: 150px;", report_xml)
            self.assertIn("padding-top: 12px;", report_xml)
            self.assertIn("max-width: 90px;", report_xml)
            self.assertIn("max-height: 90px;", report_xml)

    def test_quotation_and_invoice_show_discount_percent_and_amount(self):
        expected_snippets = (
            "ສ່ວນຫຼຸດ",
            "line.discount",
            "line.price_unit * line.product_uom_qty * line.discount / 100.0",
            "line.price_unit * line.quantity * line.discount / 100.0",
        )

        report_text = "\n".join(
            (MODULE_ROOT / "report" / filename).read_text(encoding="utf-8")
            for filename in ("sale_quotation_report.xml", "invoice_report.xml")
        )

        for snippet in expected_snippets:
            self.assertIn(snippet, report_text)

    def test_quotation_and_invoice_amounts_do_not_show_decimal_places(self):
        report_text = "\n".join(
            (MODULE_ROOT / "report" / filename).read_text(encoding="utf-8")
            for filename in ("sale_quotation_report.xml", "invoice_report.xml")
        )

        self.assertIn("'{:,.0f} {}'.format(", report_text)
        self.assertIn("'{:g}'.format(line.discount)", report_text)
        self.assertNotIn('"widget": "monetary"', report_text)

    def test_quotation_and_invoice_use_centered_signature_split(self):
        for filename in ("sale_quotation_report.xml", "invoice_report.xml"):
            report_xml = (MODULE_ROOT / "report" / filename).read_text(
                encoding="utf-8"
            )

            self.assertIn("table-layout: fixed;", report_xml)
            self.assertIn('class="ss_signature_split"', report_xml)
            self.assertIn('style="width: 50%;"', report_xml)
            self.assertIn('style="width: 50%; border-left: 1px solid #000;"', report_xml)

    def test_quotation_and_invoice_allow_multi_page_product_tables(self):
        for filename in ("sale_quotation_report.xml", "invoice_report.xml"):
            report_xml = (MODULE_ROOT / "report" / filename).read_text(
                encoding="utf-8"
            )

            self.assertIn("position: fixed;", report_xml)
            self.assertIn("top: -38mm;", report_xml)
            self.assertIn("bottom: -27mm;", report_xml)
            self.assertIn("margin: 43mm 8mm 31mm 8mm;", report_xml)
            self.assertIn("page-break-inside: auto;", report_xml)
            self.assertIn("break-inside: auto;", report_xml)
            self.assertIn('class="ss_product_row"', report_xml)
            self.assertIn(".ss_product_row", report_xml)
            self.assertIn('class="ss_summary_row"', report_xml)
            self.assertIn('class="ss_bank_row"', report_xml)
            self.assertIn('class="ss_signature_row"', report_xml)
            self.assertIn("page-break-inside: avoid;", report_xml)
            self.assertIn("break-inside: avoid;", report_xml)
            self.assertIn("line_number and line_number % 4 == 0", report_xml)
            self.assertNotIn("[3:]", report_xml)
            self.assertNotIn("extra_product_lines", report_xml)
            self.assertNotIn("max-height: 38px", report_xml)
            self.assertNotIn('class="page ss_', report_xml)
            self.assertNotIn("len(", report_xml)


if __name__ == "__main__":
    unittest.main()
