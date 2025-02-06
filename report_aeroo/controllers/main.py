# Copyright 2017 ACSONE SA/NV
# Copyright 2018 - Brain-tec AG - Carlos Jesus Cebrian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
import json

from odoo import http
from odoo.addons.web.controllers import report
from odoo.http import content_disposition, request, route
from odoo.tools import html_escape
from werkzeug.urls import url_decode


class ReportController(report.ReportController):
    MIMETYPES = {
        "txt": "text/plain",
        "html": "text/html",
        "doc": "application/vnd.ms-word",
        "odt": "application/vnd.oasis.opendocument.text",
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
        "pdf": "application/pdf",
        "sxw": "application/vnd.sun.xml.writer",
        "xls": "application/vnd.ms-excel",
    }

    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter != "aeroo":
            return super(ReportController, self).report_routes(
                reportname=reportname, docids=docids, converter=converter, **data
            )
        context = dict(request.env.context)

        if docids:
            docids = [int(i) for i in docids.split(",")]
        if data.get("options"):
            data.update(json.loads(data.pop("options")))
        if data.get("context"):
            # Ignore 'lang' here, because the context in data is the
            # one from the webclient *but* if the user explicitely wants to
            # change the lang, this mechanism overwrites it.
            data["context"] = json.loads(data["context"])
            if data["context"].get("lang"):
                del data["context"]["lang"]
            context.update(data["context"])

        # Aeroo Reports starts here
        report_obj = request.env["ir.actions.report"]
        report = report_obj._get_report_from_name(reportname)
        if context.get("print_with_sudo"):
            report = report.sudo()
        context["report_name"] = reportname
        context["return_filename"] = True
        res, extension, filename = report.with_context(**context)._render_aeroo(reportname, docids, data=data)
        mimetype = self.MIMETYPES.get(res, "application/octet-stream")
        httpheaders = [
            ("Content-Disposition", content_disposition(filename)),
            ("Content-Type", mimetype),
            ("Content-Length", len(res)),
        ]
        return request.make_response(res, headers=httpheaders)

    @route()
    def report_download(self, data, context=None):
        """This function is used by 'qwebactionmanager.js' in order to trigger
        the download of a py3o/controller report.

        :param data: a javascript array JSON.stringified containg report
        internal url ([0]) and type [1]
        :returns: Response with a filetoken cookie and an attachment header
        """
        requestcontent = json.loads(data)
        url, type = requestcontent[0], requestcontent[1]
        if type != "aeroo":
            return super(ReportController, self).report_download(data, context=context)
        try:
            reportname = url.split("/report/aeroo/")[1].split("?")[0]
            docids = None
            if "/" in reportname:
                reportname, docids = reportname.split("/")
            # on aeroo we support docids + data
            data = url_decode(url.split("?")[1]).items()
            # TODO deberiamos ver si podemos mejorar esto que va de la mano con algo que comentamos en js
            # y no parece ser lo que hacen otros. Basicamente estamos obteniendo lo que mandamos en context al imprimir
            # el reporte, desde la URl
            context = dict(data).get("context", context)
            response = self.report_routes(reportname, docids=docids, converter="aeroo", context=context)
            # if docids:
            #     # Generic report:
            #     response = self.report_routes(
            #         reportname, docids=docids, converter='aeroo')
            # else:
            #     # Particular report:
            #     # decoding the args represented in JSON
            #     data = url_decode(url.split('?')[1]).items()
            #     response = self.report_routes(
            #         reportname, converter='aeroo', **dict(data))
            return response
        except Exception as e:
            se = http.serialize_exception(e)
            error = {"code": 200, "message": "Odoo Server Error", "data": se}
            return request.make_response(html_escape(json.dumps(error)))
