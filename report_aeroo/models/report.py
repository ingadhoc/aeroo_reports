################################################################################
#
#  This file is part of Aeroo Reports software - for license refer LICENSE file
#
################################################################################

import binascii
import encodings
import logging
from base64 import b64decode

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import file_open

_logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
class ReportStylesheets(models.Model):
    """
    Aeroo Report Stylesheets
    """

    _name = "report.stylesheets"
    _description = "Report Stylesheets"

    ### Fields
    name = fields.Char(size=64, required=True)
    report_styles = fields.Binary("Template Stylesheet", help="OpenOffice.org / LibreOffice stylesheet (.odt)")
    ### ends Fields


# ------------------------------------------------------------------------------
class ResCompany(models.Model):
    _name = "res.company"
    _inherit = "res.company"

    ### Fields
    stylesheet_id = fields.Many2one("report.stylesheets", "Aeroo Reports Global Stylesheet")
    ### ends Fields


# ------------------------------------------------------------------------------
class ReportMimetypes(models.Model):
    """
    Aeroo Report Mime-Type
    """

    _name = "report.mimetypes"
    _description = "Report Mime-Types"

    ### Fields
    name = fields.Char(size=64, required=True, readonly=True)
    code = fields.Char(size=16, required=True, readonly=True)
    compatible_types = fields.Char("Compatible Mime-Types", size=128, readonly=True)
    filter_name = fields.Char(size=128, readonly=True)
    ### ends Fields


# ------------------------------------------------------------------------------
class ReportAeroo(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _render_aeroo(self, report_ref, docids, data=None):
        report = self._get_report(report_ref)
        report_parser = self.env[report.parser_model or "report.report_aeroo.abstract"]
        return report_parser.with_context(active_model=report.model, report_name=report.report_name).aeroo_report(
            docids, data
        )

    @api.model
    def _get_report_from_name(self, report_name):
        res = super()._get_report_from_name(report_name)
        if res:
            return res
        report_obj = self.env["ir.actions.report"]
        conditions = [("report_type", "in", ["aeroo"]), ("report_name", "=", report_name)]
        context = self.env["res.users"].context_get()
        return report_obj.with_context(**context).search(conditions, limit=1)

    def _read_template(self):
        self.ensure_one()
        fp = None
        data = None
        try:
            fp = file_open(self.report_file, mode="rb")
            data = fp.read()
        except OSError as e:
            if e.errno == 13:  # Permission denied on the template file
                raise UserError(_(e.strerror), e.filename)
            else:
                _logger.exception("Error in '_read_template' method", exc_info=True)
        except Exception:
            _logger.exception("Error in '_read_template' method", exc_info=True)
            fp = False
            data = False
        finally:
            if fp is not None:
                fp.close()
        return data

    @api.model
    def _get_encodings(self):
        l = list(set(encodings._aliases.values()))
        l.sort()
        return zip(l, l)

    @api.model
    def _get_default_outformat(self):
        res = self.env["report.mimetypes"].search([("code", "=", "oo-odt")])
        return res and res[0].id or False

    def _compute_extras(recs):
        result = []
        if recs.aeroo_docs_enabled():
            result.append("aeroo_ooo")
        ##### Check deferred_processing module #####
        recs.env.cr.execute(
            "SELECT id, state FROM ir_module_module WHERE \
                             name='deferred_processing'"
        )
        deferred_proc_module = recs.env.cr.dictfetchone()
        if deferred_proc_module and deferred_proc_module["state"] in ("installed", "to upgrade"):
            result.append("deferred_processing")
        ############################################
        result = ",".join(result)
        for rec in recs:
            rec.extras = result

    @api.model
    def aeroo_docs_enabled(self):
        """
        Check if Aeroo DOCS connection is enabled
        """
        icp = self.env["ir.config_parameter"].sudo()
        enabled = icp.get_param("aeroo.docs_enabled")
        return enabled == "True" and True or False

    @api.model
    def _get_in_mimetypes(self):
        mime_obj = self.env["report.mimetypes"]
        domain = self.env.context.get("allformats") and [] or [("filter_name", "=", False)]
        res = mime_obj.search(domain).read(["code", "name"])
        return [(r["code"], r["name"]) for r in res]

    ### Fields
    charset = fields.Selection("_get_encodings", required=True, default="utf_8")
    styles_mode = fields.Selection(
        [
            ("default", "Not used"),
            ("global", "Global"),
            ("specified", "Specified"),
        ],
        string="Stylesheet",
        default="default",
    )
    stylesheet_id = fields.Many2one("report.stylesheets", "Template Stylesheet")
    preload_mode = fields.Selection(
        [
            ("static", "Static"),
            ("preload", "Preload"),
        ],
        default="static",
    )
    tml_source = fields.Selection(
        [
            ("database", "Database"),
            ("file", "File"),
            ("parser", "Parser"),
            ("attachment", "Attachment"),
        ],
        string="Template source",
        default="database",
        index=True,
    )
    attachment_id = fields.Many2one("ir.attachment", domain=[("res_model", "=", "report.aeroo")], ondelete="set null")
    parser_model = fields.Char(
        help='Optional model to be used as parser, if not configured "report.report_aeroo.abstract" will be used'
    )
    report_type = fields.Selection(selection_add=[("aeroo", "Aeroo Reports")], ondelete={"aeroo": "cascade"})
    process_sep = fields.Boolean(
        "Process Separately",
        help="Generate the report for each object separately, \
              then merge reports.",
    )
    in_format = fields.Selection(
        selection="_get_in_mimetypes",
        string="Template Mime-type",
    )
    out_format = fields.Many2one("report.mimetypes", "Output Mime-type", default=_get_default_outformat)
    report_wizard = fields.Boolean(help="Adds a standard wizard when the report gets invoked.")
    copies = fields.Integer(string="Number of Copies", default=1, help="Only available if output is a pdf")
    copies_intercalate = fields.Boolean(
        help='If true, then page order will be like "1, 2, 3; 1, 2, 3", if ' 'not it will be like "1, 1; 2, 2; 3, 3"'
    )
    disable_fallback = fields.Boolean(
        "Disable Format Fallback",
        help="Raises error on format convertion failure. Prevents returning \
              original report file type if no convertion is available.",
    )
    extras = fields.Char("Extra options", compute="_compute_extras", size=256)
    deferred = fields.Selection(
        [
            ("off", "Off"),
            ("adaptive", "Adaptive"),
        ],
        help="Deferred (aka Batch) reporting, for reporting on large amount \
              of data.",
        default="off",
    )
    deferred_limit = fields.Integer(
        "Deferred Records Limit",
        help="Records limit at which you are invited to start the deferred \
              process.",
        default=80,
    )
    replace_report_id = fields.Many2one("ir.actions.report", help="Select a report that should be replaced.")
    wizard_id = fields.Many2one("ir.actions.act_window", "Wizard Action")
    report_data = fields.Binary(string="Template Content", attachment=True)
    ### ends Fields

    @api.constrains("parser_model")
    def _check_parser_model(self):
        for rec in self.filtered("parser_model"):
            if not rec.env["ir.model"].search([("name", "=", rec.parser_model)], limit=1):
                raise UserError(_("Parser model %s not found on database.") % (rec.parser_model))

    def read(self, fields=None, load="_classic_read"):
        # ugly hack to avoid report being read when we enter a view with report added on print menu
        if not fields:
            fields = list(self._fields)
            fields.remove("report_data")
            if "background_image" in fields:
                fields.remove("background_image")
            if "logo" in fields:
                fields.remove("logo")
        return super().read(fields, load=load)

    @api.onchange("in_format")
    def onchange_in_format(self):
        # TODO get first available format
        self.out_format = False

    def write(self, vals):
        # TODO remove or adapt, it shouldn't be necessary
        # if vals.get('report_type') and \
        #         orec['report_type'] != vals['report_type']:
        #     raise UserError(_("Changing report type not allowed!"))

        if "report_data" in vals and vals["report_data"]:
            try:
                b64decode(vals["report_data"])
            except binascii.Error:
                vals["report_data"] = False

        return super(ReportAeroo, self).write(vals)
