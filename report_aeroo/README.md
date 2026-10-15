Aeroo Reports
=============

Aeroo Reports prints documents (invoices, delivery slips, labels, lists) from
templates made in LibreOffice: a text document (`.odt`) or a spreadsheet
(`.ods`) with marks where the record data goes. When a report is printed, the
template is filled with the data and the file is returned.

The output can stay in the template format or be converted to PDF, Word
(`.doc`), Excel (`.xls`) or CSV. The conversion is done by an external
document service (Aeroo DOCS).

This module is the base of the Aeroo reports of other modules.

Configuration
-------------

* **Document service**: Settings > Technical > Reporting > Aeroo DOCS
  connection. Set the host, port and credentials of the service and enable it.
  Without it, reports can only be printed in the template format.
* **Global stylesheet**: on the company form, field *Aeroo Reports Global
  Stylesheet*. Stylesheets are `.odt` files loaded in Settings > Technical >
  Reporting > Report Stylesheets.

Usage
-----

Create or open a report in Settings > Technical > Reporting > Reports, set
*Format* to *Aeroo Reports* and fill the *Aeroo Configuration* tab:

* **Template source**: the template can be uploaded to the report
  (*Database*), read from a module file (*File*, path like
  `module/report/template.odt`) or taken from an attachment.
* **Template and output mime-type**: the output must be compatible with the
  template (`.odt` to `.odt`, `.doc` or PDF; `.ods` to `.ods`, `.xls`, CSV or
  PDF).
* **Number of copies** and **intercalate** (PDF output only): with 2 copies,
  intercalated pages come out 1, 2, 1, 2; otherwise 1, 1, 2, 2.
* **Stylesheet**: none, the company global one, or a specific one.
* **Parser model**: an abstract model that inherits
  `report.report_aeroo.abstract` to add data or functions to the template.
* **Process separately** (PDF output only): with several records, one document
  is generated per record and the PDFs are merged.
* **Disable format fallback**: raise an error when the conversion fails,
  instead of returning the file in the template format.

The report is printed from the *Print* menu of the model, like any other
report. The file name follows *Printed Report Name*.

The *Preload*, *Deferred* and *Replace Report* options and the *Generic*
template type are kept for compatibility and have no effect.

Credits
-------

Aeroo Reports is based on the original work of Alistek
(http://www.alistek.com) and Simone Orsi (Domsense). Port to Odoo sponsored by
ADHOC, FlectraHQ, BESCO, Serpent CS and CYSFuturo.

Maintained by ADHOC SA (https://www.adhoc.com.ar).
