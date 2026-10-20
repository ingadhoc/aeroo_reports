import warnings

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReportAeroo(TransactionCase):
    def test_render_twice_in_one_transaction(self):
        """Environments are shared by context within a transaction: a second render
        must not reuse the environment the first one wrote its attributes on."""
        report = self.env["ir.actions.report"].create(
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
            }
        )
        partners = self.env["res.partner"].create([{"name": "Aeroo A"}, {"name": "Aeroo B"}])
        reports = report.with_context(report_name=report.report_name, lang="en_US")
        # genshi (third party) emits DeprecationWarning on Python 3.14
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = [reports._render_aeroo(report.report_name, partner.ids) for partner in partners]
        for content, ext in results:
            self.assertEqual(ext, "odt")
            self.assertTrue(content)
