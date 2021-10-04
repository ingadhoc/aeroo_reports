##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, exceptions, models, _


class IrActionsReport(models.Model):

    _inherit = 'ir.actions.report'

    @api.multi
    def print_document(self, record_ids, data=None):
        """ This method is called from the print actions (controller).
        Every time ir.action.print is called.
        ir.actions.report, everytime someone click Print button

        This overwrite let us to proper render aeroo report's when printing
        from server
        """
        if self.report_type == 'aeroo':
            document, doc_format, _filename = self.with_context(
                must_skip_send_to_printer=True).render_aeroo(
                    record_ids, data=data)
            behaviour = self.behaviour()
            printer = behaviour.pop('printer', None)
            if not printer:
                raise exceptions.Warning(
                    _('No printer configured to print this report.')
                )
            # TODO should we use doc_format instead of report_type
            return printer.print_document(
                self, document, doc_format=self.report_type, **behaviour)

        return super(IrActionsReport, self).print_document(
            record_ids, data=data)

    def render_qweb_pdf(self, docids, data=None):
        """ This method is called directly from another places in odoo like
        portal, website, pos, email template attachments, etc.

        In this case we do not want to print using the printer. With this
        change we avoid to print the report in the printer
        """
        # NOTE: Por ahora no extendemos "render_aeroo" de manera analoga a como
        # extendemos a "render_qweb_pdf" porque en realidad no queremos que
        # desde los lugares donde se llama directamente a "render_qweb_pdf" se
        # mande a impresora (portal, plantilla de email, etc), tal vez sea
        # interesante hacerlo para pos."
        return super(IrActionsReport, self.with_context(
            must_skip_send_to_printer=True)).render_qweb_pdf(
            docids, data=data)
