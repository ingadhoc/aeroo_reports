import warnings

from odoo.tests import TransactionCase, tagged
from odoo.tools import BinaryBytes, file_open


@tagged("post_install", "-at_install")
class TestReportAeroo(TransactionCase):
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
