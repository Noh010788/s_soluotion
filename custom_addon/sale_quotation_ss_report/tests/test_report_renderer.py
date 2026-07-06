import importlib.util
import unittest
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = MODULE_ROOT / "models" / "report_renderer.py"


def load_renderer_module():
    spec = importlib.util.spec_from_file_location("ss_report_renderer", RENDERER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestReportRendererSelection(unittest.TestCase):
    def test_custom_reports_use_weasyprint(self):
        renderer = load_renderer_module()

        for report_name in (
            "sale.report_saleorder",
            "stock.report_deliveryslip",
            "account.report_invoice_with_payments",
        ):
            self.assertTrue(renderer.is_weasyprint_report(report_name))

    def test_unrelated_reports_keep_wkhtmltopdf(self):
        renderer = load_renderer_module()

        self.assertFalse(renderer.is_weasyprint_report("purchase.report_purchaseorder"))

    def test_page_css_preserves_a4_margins_and_orientation(self):
        renderer = load_renderer_module()

        css = renderer.build_page_css(
            page_format="A4",
            orientation="Portrait",
            margin_top=5,
            margin_right=8,
            margin_bottom=5,
            margin_left=8,
        )

        self.assertEqual(
            css,
            "@page { size: A4 portrait; margin: 5mm 8mm 5mm 8mm; }",
        )

    def test_font_css_uses_local_phetsarath_files(self):
        renderer = load_renderer_module()

        css = renderer.build_font_css(
            regular_url="file:///module/fonts/Phetsarath_OT.ttf",
            bold_url="file:///module/fonts/Phetsarath_OT_Bold.ttf",
        )

        self.assertIn('font-family: "Phetsarath OT"', css)
        self.assertIn("file:///module/fonts/Phetsarath_OT.ttf", css)
        self.assertIn("file:///module/fonts/Phetsarath_OT_Bold.ttf", css)
        self.assertIn("font-weight: 700", css)


if __name__ == "__main__":
    unittest.main()
