###############################################################################
#
#  This file is part of Aeroo Reports software - for license refer LICENSE file
#
###############################################################################

import base64
import binascii
import datetime
import logging
import time
from base64 import b64decode
from io import BytesIO

import aeroolib as aeroolib
import babel.dates
import pytz
from aeroolib import __version__ as aeroolib_version
from aeroolib.plugins.opendocument import OOSerializer, Template, _filter
from currency2text import supported_language
from genshi.template.eval import StrictLookup
from odoo import (
    _,
    api,
    fields,
    models,
    release as odoo_release,
    tools as tools,
)
from odoo.exceptions import MissingError
from odoo.modules.module import load_manifest
from odoo.tools import frozendict

# for format_datetime
from odoo.tools.misc import (
    DATE_LENGTH,
    format_date as odoo_fd,
    formatLang as odoo_fl,
    get_lang,
    posix_to_ldml,
)
from odoo.tools.safe_eval import (
    safe_eval,
    time as safeval_time,
)
from PIL import Image, UnidentifiedImageError
from PyPDF2 import PdfFileReader, PdfFileWriter

from .docs_client_lib import DOCSConnection
from .exceptions import ConnectionError


def format_datetime(env, value, lang_code=False, date_format=False, tz="America/Argentina/Buenos_Aires"):
    """
    This is an adaptation of odoo format_date method but to format
    datetimes
    TODO we should move it to another plase or make it simpler

    :param env: an environment.
    :param date, datetime or string value: the date to format.
    :param string lang_code: the lang code, if not specified it is
        extracted from the environment context.
    :param string date_format: the format or the date (LDML format),
      if not specified the default format of the lang.
    :return: date formatted in the specified format.
    :rtype: string
    """
    if not value:
        return ""
    if isinstance(value, str):
        if len(value) < DATE_LENGTH:
            return ""
        if len(value) > DATE_LENGTH:
            # a datetime, convert to correct timezone
            value = fields.Datetime.from_string(value)
            value = fields.Datetime.context_timestamp(env["res.lang"], value)
        else:
            value = fields.Datetime.from_string(value)

    lang = env["res.lang"]._lang_get(lang_code or env.context.get("lang") or "en_US")
    locale = babel.Locale.parse(lang.code)
    if not date_format:
        date_format = posix_to_ldml("%s %s" % (lang.date_format, lang.time_format), locale=locale)

    return babel.dates.format_datetime(value, format=date_format, locale=locale, tzinfo=tz)


_logger = logging.getLogger(__name__)

mime_dict = {
    "oo-odt": "odt",
    "oo-ods": "ods",
    "oo-pdf": "pdf",
    "oo-doc": "doc",
    "oo-xls": "xls",
    "oo-csv": "csv",
}


class ReportAerooAbstract(models.AbstractModel):
    _name = "report.report_aeroo.abstract"
    _description = "report.report_aeroo.abstract"

    def __filter(self, val):
        if isinstance(val, models.BaseModel) and val:
            return val._compute_display_name()
        return _filter(val)

    # Extra Functions ==================================================
    def myset(self, pair):
        if isinstance(pair, dict):
            self.env.localcontext["storage"].update(pair)
        return False

    def myget(self, key):
        if key in self.env.localcontext["storage"] and self.env.localcontext["storage"][key]:
            return self.env.localcontext["storage"][key]
        return False

    def partner_address(self, partner):
        # for backward compatibility
        ret = ""
        if partner.street:
            ret += partner.street
        if partner.street2:
            if partner.street:
                ret += " - " + partner.street2
            else:
                ret += partner.street2
        if ret != "":
            ret += ". "

        if partner.zip:
            ret += "(" + partner.zip + ")"
        if partner.city:
            if partner.zip:
                ret += " " + partner.city
            else:
                ret += partner.city
        if partner.state_id:
            if partner.city:
                ret += " - " + partner.state_id.name
            else:
                ret += partner.state_id.name
        if partner.zip or partner.city or partner.state_id:
            ret += ". "

        if partner.country_id:
            ret += partner.country_id.name + "."

        return ret

    def _asarray(self, attr, field):
        """
        Returns named field from all objects as a list.
        """
        expr = "for o in objects:\n\tvalue_list.append(o.%s)" % field
        localspace = {"objects": attr, "value_list": []}
        exec(expr, localspace)
        return localspace["value_list"]

    def _average(self, attr, field):
        """
        Returns average (arithmetic mean) of fields from all objects in a list.
        """
        expr = "for o in objects:\n\tvalue_list.append(o.%s)" % field
        localspace = {"objects": attr, "value_list": []}
        exec(expr, localspace)
        x = sum(localspace["value_list"])
        y = len(localspace["value_list"])
        return float(x) / float(y)

    def _asimage(
        self, field_value, rotate=None, size_x=None, size_y=None, dpix=96, dpiy=96, uom="px", hold_ratio=False
    ):
        """
        Prepare image for inserting into OpenOffice.org document
        """

        def size_by_uom(val, uom, dpi):
            if uom == "px":
                result = str(val / dpi) + "in"
            elif uom == "cm":
                result = str(val / 2.54) + "in"
            elif uom == "in":
                result = str(val) + "in"
            return result

        ##############################################
        if not field_value:
            return BytesIO(), "image/png"
        try:
            field_value = b64decode(field_value)
            tf = BytesIO(field_value)
            tf.seek(0)
            im = Image.open(tf)
            im.verify()  # Verifica que el archivo es una imagen válida
        except (binascii.Error, UnidentifiedImageError):
            _logger.exception("Invalid image data")
            return BytesIO(), "image/png"
        tf.seek(0)
        im = Image.open(tf)
        format = im.format.lower()
        # usamos dpi fijos porque si no en determinados casos nos achica o
        # agranda mucho las imagenes en los reportes (al menos el logo)
        # dpi_x, dpi_y = map(float, im.info.get('dpi', (96, 96)))
        dpi_x, dpi_y = map(float, (dpix, dpiy))
        try:
            if rotate is not None:
                im = im.rotate(int(rotate))
                tf.seek(0)
                im.save(tf, format)
        except Exception:
            _logger.exception("Error in '_asimage' method")

        if hold_ratio:
            img_ratio = im.size[0] / float(im.size[1])
            if size_x and not size_y:
                size_y = size_x / img_ratio
            elif not size_x and size_y:
                size_x = size_y * img_ratio
            elif size_x and size_y:
                size_y2 = size_x / img_ratio
                size_x2 = size_y * img_ratio
                if size_y2 > size_y:
                    size_x = size_x2
                elif size_x2 > size_x:
                    size_y = size_y2

        size_x = size_x and size_by_uom(size_x, uom, dpi_x) or str(im.size[0] / dpi_x) + "in"
        size_y = size_y and size_by_uom(size_y, uom, dpi_y) or str(im.size[1] / dpi_y) + "in"
        return tf, "image/%s" % format, size_x, size_y

    def _currency_to_text(self, currency):
        def c_to_text(sum, currency=currency, language=None):
            lang = supported_language.get(language or self._get_lang())
            return str(lang.currency_to_text(sum, currency), "UTF-8")

        return c_to_text

    def _get_selection_items(self, kind="items"):
        def get_selection_item(obj, field, value=None):
            try:
                # TODO how to check for list of objects in new API?
                if isinstance(obj, models.AbstractModel):
                    obj = obj[0]
                if isinstance(obj, str):
                    model = obj
                    field_val = value
                else:
                    model = obj._name
                    field_val = getattr(obj, field)
                val = self.env[model].fields_get(allfields=[field])[field]["selection"]
                if kind == "item":
                    if field_val:
                        return dict(val)[field_val]
                elif kind == "items":
                    return val
                return ""
            except Exception:
                _logger.exception("Error in '_get_selection_item' method", exc_info=True)
                return ""

        return get_selection_item

    def _get_log(self, obj, field=None):
        if field:
            return obj.get_metadata()[0][field]
        else:
            return obj.get_metadata()[0]

    # / Extra Functions ======================================================

    def get_docs_conn(self):
        icp = self.env.get("ir.config_parameter").sudo()
        icpgp = icp.get_param
        docs_host = icpgp("aeroo.docs_host") or "localhost"
        docs_port = icpgp("aeroo.docs_port") or "8989"
        # docs_auth_type = icpgp('aeroo.docs_auth_type') or False
        docs_username = icpgp("aeroo.docs_username") or "anonymous"
        docs_password = icpgp("aeroo.docs_password") or "anonymous"
        return DOCSConnection(docs_host, docs_port, username=docs_username, password=docs_password)

    def _generate_doc(self, data, report):
        docs = self.get_docs_conn()
        # token = docs.upload(data)
        if report.out_format.code == "oo-dbf":
            data = docs.convert(
                # identifier=token
                data=data
            )  # TODO What format?
        else:
            data = docs.convert(
                # identifier=token,
                data=data,
                out_mime=mime_dict[report.out_format.code],
                in_mime=mime_dict[report.in_format],
            )

        # TODO this copies method could go to a generic module because it just
        # manipulates the outgoing pdf report
        if mime_dict[report.out_format.code] == "pdf" and report.copies > 1:
            output = PdfFileWriter()
            reader = PdfFileReader(BytesIO(data))
            copies_intercalate = report.copies_intercalate
            copies = report.copies
            if copies_intercalate:
                for copy in range(copies):
                    for page in range(reader.getNumPages()):
                        output.addPage(reader.getPage(page))
            else:
                for page in range(reader.getNumPages()):
                    for copy in range(copies):
                        output.addPage(reader.getPage(page))
            s = BytesIO()
            output.write(s)
            data = s.getvalue()

        return data

    def _get_lang(self, source="current"):
        if source == "current":
            return self.env.context["lang"] or self.env.context["user_lang"]
        elif source == "company":
            return self.env.company.partner_id.lang
        elif source == "user":
            return self.env.context["user_lang"]

    def _set_lang(self, lang, obj=None):
        self.env.localcontext.update(lang=lang)
        if obj is None and "objects" in self.env.localcontext:
            obj = self.env.localcontext["objects"]
        if obj and obj.env.context["lang"] != lang:
            ctx_copy = dict(self.env.context)
            ctx_copy.update(lang=lang)
            obj.env.context = frozendict(ctx_copy)
            # desactivamos el invalidate_cache porque rompe mail compose cuando
            # el idioma del partner de la compañia del usuario
            # (obj.env.context['lang']) es distinta al idioma del modelo (lang)
            # y tampoco vimos necesidad de este invalidate_cache por ahora
            # obj.invalidate_cache()

    def _format_lang(
        self,
        value,
        digits=2,
        grouping=True,
        monetary=False,
        dp=False,
        currency_obj=False,
        date=False,
        date_time=False,
        lang_code=False,
        date_format=False,
    ):
        """We add date and date_time for backwards compatibility. Odoo has
        split the method in two (formatlang and format_date)
        """
        if date:
            # we force the timezone of the user if the value is datetime
            if isinstance(value, (datetime.datetime)):
                value = value.astimezone(pytz.timezone(self.env.user.tz or "UTC"))
            return odoo_fd(self.env, value, lang_code=lang_code, date_format=date_format)
        elif date_time:
            return format_datetime(self.env, value, lang_code=lang_code, date_format=date_format, tz=self.env.user.tz)
        return odoo_fl(self.env, value, digits, grouping, monetary, dp, currency_obj)

    def _set_objects(self, model, docids):
        _logger.log(25, "AEROO setobjects======================= %s - %s", model, docids)
        lctx = self.env.localcontext
        lang = lctx["lang"]
        objects = None
        env_lang = self.env.user.lang or get_lang(self.env).code
        if env_lang != lang:
            ctx_copy = dict(self.env.context)
            ctx_copy.update(lang=lang)
            objects = self.env.get(model).with_context(**ctx_copy).browse(docids)
        else:
            objects = self.env.get(model).browse(docids)
        lctx["objects"] = objects
        lctx["o"] = objects and objects[0] or None
        _logger.log(25, "AEROO setobjects======================= %s", lang)

    def test(self, obj):
        _logger.exception("AEROO TEST1======================= %s - %s" % (type(obj), id(obj)))
        _logger.exception("AEROO TEST2======================= %s" % (obj,))

    def get_other_template(self, model, rec_id):
        if not hasattr(self, "get_template"):
            return False
        record = self.env.get(model).browse(rec_id)
        template = self.get_template(record)
        return template

    def get_stylesheet(self, report):
        style_io = None
        if report.styles_mode != "default":
            if report.styles_mode == "global":
                styles = self.env.company.stylesheet_id
            elif report.styles_mode == "specified":
                styles = report.stylesheet_id
            if styles:
                style_io = b64decode(styles.report_styles or False)
        return style_io

    def complex_report(self, docids, data, report, ctx):
        """Returns an aeroo report generated by aeroolib"""

        self.env.model = ctx.get("active_model", False)
        self.env.report = report

        # ====================================================================
        def barcode(barcode_type, value, width=600, height=100, dpi_x=96, dpi_y=96, humanreadable=0):
            # TODO check that asimage and barcode both accepts width and height
            img = self.env["ir.actions.report"].barcode(
                barcode_type, value, width=width, height=height, humanreadable=humanreadable
            )
            return self._asimage(base64.b64encode(img), dpix=dpi_x, dpiy=dpi_y)

        self.env.localcontext = {
            "myset": self.myset,
            "myget": self.myget,
            "partner_address": self.partner_address,
            "storage": {},
            "user": self.env.user,
            "user_lang": ctx.get("lang", self.env.user.lang),
            "data": data,
            "time": time,
            "datetime": datetime,
            "average": self._average,
            "currency_to_text": self._currency_to_text,
            "asimage": self._asimage,
            "get_selection_item": self._get_selection_items("item"),
            "get_selection_items": self._get_selection_items(),
            "get_log": self._get_log,
            "asarray": self._asarray,
            "__filter": self.__filter,  # Don't use in the report template!
            "getLang": self._get_lang,
            "setLang": self._set_lang,
            "formatLang": self._format_lang,
            "test": self.test,
            "fields": fields,
            "company": self.env.company,
            "barcode": barcode,
            "tools": tools,
        }
        self.env.localcontext.update(ctx)
        self._set_lang(self.env.company.partner_id.lang)
        self._set_objects(self.env.model, docids)

        file_data = None
        if report.tml_source == "database":
            if not report.report_data or report.report_data == "False":
                # TODO log report ID etc.
                raise MissingError(_("Aeroo Reports could'nt find report template"))
            file_data = b64decode(report.report_data)
        elif report.tml_source == "file":
            if not report.report_file or report.report_file == "False":
                # TODO log report ID etc.
                raise MissingError(_("No Aeroo Reports template filename provided"))
            file_data = report._read_template()
        elif report.tml_source == "attachment":
            file_data = b64decode(report.attachment_id.datas)
        else:
            rec_id = ctx.get("active_id", data.get("id")) or data.get("id")
            file_data = self.get_other_template(self.env.model, rec_id)

        if not file_data:
            # TODO log report ID etc.
            raise MissingError(_("Aeroo Reports could'nt find report template"))

        template_io = BytesIO(file_data)
        if report.styles_mode == "default":
            serializer = OOSerializer(template_io)
        else:
            style_io = BytesIO(self.get_stylesheet(report))
            serializer = OOSerializer(template_io, oo_styles=style_io)

        basic = Template(source=template_io, serializer=serializer, lookup=StrictLookup)

        # Add metadata
        ser = basic.Serializer
        model_obj = self.env.get("ir.model")
        model_name = model_obj.sudo().search([("model", "=", self.env.model)])[0].name
        ser.add_title(model_name)

        user_name = self.env.user.name
        ser.add_creation_user(user_name)

        module_info = load_manifest("report_aeroo")
        version = module_info["version"]
        ser.add_generator_info("Aeroo Lib/%s Aeroo Reports/%s" % (aeroolib_version, version))
        ser.add_custom_property("Aeroo Reports %s" % version, "Generator")
        ser.add_custom_property("Odoo %s" % odoo_release.version, "Software")
        ser.add_custom_property(module_info["website"], "URL")
        ser.add_creation_date(time.strftime("%Y-%m-%dT%H:%M:%S"))

        file_data = basic.generate(**self.env.localcontext).render().getvalue()
        # ======================================================================
        code = mime_dict[report.in_format]
        # _logger.info("End process %s (%s), elapsed time: %s" % (
        #     self.name, self.env.model, time.time() - aeroo_print.start_time),
        #     logging.INFO)  # debug mode

        return file_data, code

    def simple_report(self, docids, data, report, ctx, output="raw"):
        pass

    def single_report(self, docids, data, report, ctx):
        code = report.out_format.code
        # ext = mime_dict[code]
        if code.startswith("oo-"):
            return self.complex_report(docids, data, report, ctx)
        elif code == "genshi-raw":
            return self.simple_report(docids, data, report, ctx, output="raw")

    def assemble_tasks(self, docids, data, report, ctx):
        code = report.out_format.code
        result = self.single_report(docids, data, report, ctx)
        return_filename = self._context.get("return_filename")

        print_report_name = "report"
        if report.print_report_name and not len(docids) > 1:
            obj = self.env[report.model].browse(docids)
            print_report_name = safe_eval(report.print_report_name, {"object": obj, "time": safeval_time})

        if report.in_format == code:
            filename = "%s.%s" % (print_report_name, mime_dict[report.in_format])
            return return_filename and (result[0], result[1], filename) or (result[0], result[1])
        else:
            try:
                result = self._generate_doc(result[0], report)
                filename = "%s.%s" % (print_report_name, mime_dict[report.out_format.code])
                return return_filename and (result, mime_dict[code], filename) or (result, mime_dict[code])
            except Exception as e:
                _logger.exception(_("Aeroo DOCS error!\n%s") % str(e))
                if report.disable_fallback:
                    result = None
                    _logger.exception(e[0])
                    raise ConnectionError(_("Could not connect Aeroo DOCS!"))
        # only if fallback
        filename = "%s.%s" % (print_report_name, mime_dict[report.in_format])
        return return_filename and (result[0], result[1], filename) or (result[0], result[1])

    @api.model
    def aeroo_report(self, docids, data):
        report_name = self._context.get("report_name")
        report = self.env["ir.actions.report"]._get_report_from_name(report_name)
        # TODO
        # _logger.info("Start Aeroo Reports %s (%s)" % (
        #     name, ctx.get('active_model')),
        #     logging.INFO)  # debug mode

        if "tz" not in self._context:
            self = self.with_context(tz=self.env.user.tz)

        # TODO we should propagate context in the proper way, just with self

        # agregamos el process_sep aca ya que necesitamos el doc convertido
        # para poder unirlos
        if report.process_sep and len(docids) > 1:
            # por ahora solo soportamos process_sep para pdf, en version
            # anterior tambien soportaba algun otro
            code = report.out_format.code
            if code != "oo-pdf":
                raise MissingError(_("Process_sep not compatible with selected output format"))

            results = []
            for docid in docids:
                results.append(self.assemble_tasks([docid], data, report, self._context))
            output = PdfFileWriter()
            for r in results:
                reader = PdfFileReader(BytesIO(r[0]))
                for page in range(reader.getNumPages()):
                    output.addPage(reader.getPage(page))
            s = BytesIO()
            output.write(s)
            data = s.getvalue()
            res = self._context.get("return_filename") and (data, results[0][1], results[0][2]) or (data, results[0][1])
        else:
            res = self.assemble_tasks(docids, data, report, self._context)
        # TODO
        # _logger.info("End Aeroo Reports %s (%s), total elapsed time: %s" %
        #              (name, model, time() - aeroo_print.start_total_time),
        #              logging.INFO)  # debug mode

        return res

    # @api.model
    # def get_report_values(self, docids, data=None):
    #     # report = self.env['ir.actions.report']._get_report_from_name(
    #     #     'account_test.report_accounttest')
    #     # records = self.env['accounting.assert.test'].browse(self.ids)
    #     return {
    #         # 'doc_ids': self._ids,
    #         'doc_ids': docids,
    #         # 'doc_model': report.model,
    #         # 'docs': records,
    #         'data': data,
    #         # 'execute_code': self.execute_code,
    #         # 'datetime': datetime
    #     }
