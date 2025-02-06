################################################################################
#
#  This file is part of Aeroo Reports software - for license refer LICENSE file
#
################################################################################

{
    "name": "Aeroo Reports",
    "version": "18.0.1.0.0",
    "category": "Generic Modules/Aeroo Reports",
    "summary": "Enterprise grade reporting solution",
    "author": "Alistek",  # pylint: disable=manifest-required-author
    "website": "http://www.alistek.com",
    "complexity": "easy",
    "depends": ["base", "web", "mail"],
    "demo": [
        "demo/report_sample.xml",
    ],
    "data": [
        "views/report_view.xml",
        "data/report_aeroo_data.xml",
        "wizard/installer.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "report_aeroo/static/src/js/report/reportactionmanager.js",
        ],
    },
    "license": "GPL-3 or any later version",
    "installable": True,
    "application": True,
    "auto_install": False,
}
