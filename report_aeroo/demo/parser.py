################################################################################
#
#  This file is part of Aeroo Reports software - for license refer LICENSE file
#
################################################################################

from odoo import api, models


class Parser(models.AbstractModel):
    _inherit = "report.report_aeroo.abstract"

    _name = "report.sample_report"
    _description = "report.sample_report"

    @api.model
    def aeroo_report(self, docids, data):
        self = self.with_context(test_parser="parser works ok!")
        return super(Parser, self).aeroo_report(docids, data)
