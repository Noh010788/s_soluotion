import io
import logging
from pathlib import Path

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.pdf import PdfFileReader, PdfFileWriter

from .report_renderer import build_font_css, build_page_css, is_weasyprint_report


_logger = logging.getLogger(__name__)
_FONT_DIR = Path(__file__).resolve().parents[1] / "static" / "src" / "fonts"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _run_weasyprint(self, bodies, report, landscape=False):
        try:
            from weasyprint import CSS, HTML
            from weasyprint.text.fonts import FontConfiguration
        except ImportError as error:
            raise UserError(
                "WeasyPrint is required to render the Lao PDF reports."
            ) from error

        paperformat = report.get_paperformat()
        orientation = "Landscape" if landscape else paperformat.orientation
        page_css = build_page_css(
            page_format=paperformat.format or "A4",
            orientation=orientation,
            margin_top=paperformat.margin_top,
            margin_right=paperformat.margin_right,
            margin_bottom=paperformat.margin_bottom,
            margin_left=paperformat.margin_left,
        )
        font_css = build_font_css(
            regular_url=(_FONT_DIR / "Phetsarath_OT.ttf").as_uri(),
            bold_url=(_FONT_DIR / "Phetsarath_OT_Bold.ttf").as_uri(),
        )
        font_config = FontConfiguration()
        stylesheets = [
            CSS(string=page_css, font_config=font_config),
            CSS(string=font_css, font_config=font_config),
        ]
        base_url = self._get_report_url()

        rendered_pdfs = [
            HTML(string=body, base_url=base_url).write_pdf(
                stylesheets=stylesheets,
                font_config=font_config,
            )
            for body in bodies
        ]
        if len(rendered_pdfs) == 1:
            return rendered_pdfs[0]

        writer = PdfFileWriter()
        for pdf_content in rendered_pdfs:
            reader = PdfFileReader(io.BytesIO(pdf_content))
            for page in reader.pages:
                writer.add_page(page)

        result = io.BytesIO()
        writer.write(result)
        return result.getvalue()

    def _run_wkhtmltopdf(
        self,
        bodies,
        report_ref=False,
        header=None,
        footer=None,
        landscape=False,
        specific_paperformat_args=None,
        set_viewport_size=False,
    ):
        report = self._get_report(report_ref) if report_ref else self
        if is_weasyprint_report(report.report_name):
            _logger.info(
                "Rendering report %s with WeasyPrint for Lao text shaping",
                report.report_name,
            )
            return self._run_weasyprint(bodies, report, landscape=landscape)

        return super()._run_wkhtmltopdf(
            bodies,
            report_ref=report_ref,
            header=header,
            footer=footer,
            landscape=landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size,
        )
