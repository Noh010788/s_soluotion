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


if __name__ == "__main__":
    unittest.main()
