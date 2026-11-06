import warnings
from io import BytesIO
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.tools import BinaryBytes, file_open
from odoo.tools.pdf import PdfFileReader, PdfFileWriter


class FakeDocs:
    """Stands in for the Aeroo Docs service: hands back a known PDF per call, converting nothing."""

    def __init__(self, pdfs):
        self._pdfs = pdfs

    def convert(self, data=None, out_mime=None, in_mime=None):
        return self._pdfs.pop(0)


@tagged("post_install", "-at_install")
class TestReportAeroo(TransactionCase):
    # a blank page carries no text to read back, so each page is identified by its size
    PAGES = [(300, 400), (301, 401), (302, 402), (303, 403)]

    def _create_report(self, **vals):
        return self.env["ir.actions.report"].create(
            {
                "name": "Aeroo test report",
                "model": "res.partner",
                "report_name": "res.partner.aeroo_test_report",
                "report_type": "aeroo",
                "tml_source": "file",
                "report_file": "report_aeroo/demo/template.odt",
                "parser_model": "report.sample_report",
                "in_format": "oo-odt",
                "out_format": self.env.ref("report_aeroo.report_mimetypes_odt_odt").id,
                **vals,
            }
        )

    def _render(self, report):
        reports = report.with_context(report_name=report.report_name, lang="en_US")
        partner = self.env["res.partner"].create([{"name": "Aeroo A"}])
        # genshi (third party) emits DeprecationWarning on Python 3.14
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return reports._render_aeroo(report.report_name, partner.ids)

    def _template(self):
        with file_open("report_aeroo/demo/template.odt", "rb") as template:
            return template.read()

    def _pdf(self, pages):
        writer = PdfFileWriter()
        for width, height in pages:
            writer.add_blank_page(width=width, height=height)
        stream = BytesIO()
        writer.write(stream)
        return stream.getvalue()

    def _pages(self, pdf):
        reader = PdfFileReader(BytesIO(pdf), strict=False)
        return [(round(float(page.mediabox.width)), round(float(page.mediabox.height))) for page in reader.pages]

    def _render_pdf(self, report, partners, pdfs):
        """Render through a stubbed docs service: the PDF only exists once the template is converted."""
        reports = report.with_context(report_name=report.report_name, lang="en_US")
        pending = list(pdfs)
        parser = type(self.env[report.parser_model])
        with patch.object(parser, "get_docs_conn", lambda self: FakeDocs(pending)):
            # genshi (third party) emits DeprecationWarning on Python 3.14
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                return reports._render_aeroo(report.report_name, partners.ids)

    def test_render_template_from_database(self):
        """A template uploaded on the report renders, instead of being read as base64."""
        report = self._create_report(tml_source="database", report_data=BinaryBytes(self._template()))
        content, ext = self._render(report)
        self.assertEqual(ext, "odt")
        self.assertTrue(content)

    def test_render_template_from_attachment(self):
        """A template taken from an attachment renders: 20 dropped ir.attachment.datas."""
        attachment = self.env["ir.attachment"].create(
            {"name": "template.odt", "res_model": "report.aeroo", "raw": BinaryBytes(self._template())}
        )
        report = self._create_report(tml_source="attachment", attachment_id=attachment.id)
        content, ext = self._render(report)
        self.assertEqual(ext, "odt")
        self.assertTrue(content)

    def test_render_with_stylesheet(self):
        """A report with its own stylesheet renders, instead of being read as base64."""
        stylesheet = self.env["report.stylesheets"].create(
            {"name": "Aeroo test stylesheet", "report_styles": BinaryBytes(self._template())}
        )
        report = self._create_report(styles_mode="specified", stylesheet_id=stylesheet.id)
        content, ext = self._render(report)
        self.assertEqual(ext, "odt")
        self.assertTrue(content)

    def test_docs_config_wizard(self):
        """The Aeroo Docs settings wizard opens: its banner is a BinaryValue, not bytes."""
        wizard = self.env["docs_config.installer"].create({})
        self.assertTrue(wizard.config_logo)

    def test_render_twice_in_one_transaction(self):
        """Environments are shared by context within a transaction: a second render
        must not reuse the environment the first one wrote its attributes on."""
        report = self._create_report()
        partners = self.env["res.partner"].create([{"name": "Aeroo A"}, {"name": "Aeroo B"}])
        reports = report.with_context(report_name=report.report_name, lang="en_US")
        # genshi (third party) emits DeprecationWarning on Python 3.14
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = [reports._render_aeroo(report.report_name, partner.ids) for partner in partners]
        for content, ext in results:
            self.assertEqual(ext, "odt")
            self.assertTrue(content)

    def test_pdf_copies_order(self):
        """Several copies of a PDF come out interleaved (1, 2, 1, 2) or grouped by page (1, 1, 2, 2),
        depending on the report: 20 walks the pages with reader.pages / add_page, not PyPDF2."""
        first, second = self.PAGES[0], self.PAGES[1]
        cases = [
            ("interleaved: one whole copy after the other", True, [first, second, first, second]),
            ("not interleaved: the copies of each page together", False, [first, first, second, second]),
        ]
        for label, intercalate, expected in cases:
            with self.subTest(label):
                report = self._create_report(
                    # the parser looks the report up by name, so each case needs its own
                    report_name="res.partner.aeroo_copies_%s" % intercalate,
                    out_format=self.env.ref("report_aeroo.report_mimetypes_pdf_odt").id,
                    copies=2,
                    copies_intercalate=intercalate,
                )
                partner = self.env["res.partner"].create([{"name": "Aeroo A"}])
                content, ext = self._render_pdf(report, partner, [self._pdf([first, second])])
                self.assertEqual(ext, "pdf")
                self.assertEqual(self._pages(content), expected)

    def test_process_sep_joins_the_documents(self):
        """With "process separately", each record is rendered on its own and the PDFs are joined
        in order into a single document."""
        report = self._create_report(
            out_format=self.env.ref("report_aeroo.report_mimetypes_pdf_odt").id,
            process_sep=True,
        )
        partners = self.env["res.partner"].create([{"name": "Aeroo A"}, {"name": "Aeroo B"}])
        content, ext = self._render_pdf(report, partners, [self._pdf(self.PAGES[:2]), self._pdf(self.PAGES[2:])])
        self.assertEqual(ext, "pdf")
        self.assertEqual(self._pages(content), self.PAGES)
