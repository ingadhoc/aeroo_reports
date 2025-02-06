##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, exceptions, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def print_document(self, record_ids, data=None):
        """This method is called from the print actions (controller).
        Every time ir.action.print is called.
        ir.actions.report, everytime someone click Print button

        This overwrite let us to proper render aeroo report's when printing
        from server
        """
        if self.report_type == "aeroo":
            document, doc_format = self.with_context(must_skip_send_to_printer=True)._render_aeroo(
                self.report_name, record_ids, data=data
            )
            behaviour = self.behaviour()
            printer = behaviour.pop("printer", None)
            if not printer:
                raise exceptions.Warning(_("No printer configured to print this report."))
            # TODO chequear que nosotros estamos haciendo igual que en
            # https://github.com/OCA/report-print-send/blob/13.0/base_report_to_printer/models/ir_actions_report.py#L111
            # pero en realidad luego pareciera que doc_format no es interpretado en
            # https://github.com/OCA/report-print-send/blob/14.0/base_report_to_printer/models/printing_printer.py#L134
            return printer.print_document(self, document, doc_format=doc_format, **behaviour)

        return super(IrActionsReport, self).print_document(record_ids, data=data)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """This method is called directly from another places in odoo like
        portal, website, pos, email template attachments, etc.

        In this case we do not want to print using the printer. With this
        change we avoid to print the report in the printer
        """
        # NOTE: Por ahora no extendemos "render_aeroo" de manera analoga a como
        # extendemos a "render_qweb_pdf" porque en realidad no queremos que
        # desde los lugares donde se llama directamente a "render_qweb_pdf" se
        # mande a impresora (portal, plantilla de email, etc), tal vez sea
        # interesante hacerlo para pos."
        return super(IrActionsReport, self.with_context(must_skip_send_to_printer=True))._render_qweb_pdf(
            report_ref=report_ref, res_ids=res_ids, data=data
        )
