################################################################################
#
#  This file is part of Aeroo Reports software - for license refer LICENSE file
#
################################################################################
from . import controllers
from . import models
from . import report_parser

from . import report
from . import demo

from . import wizard

check_list = [
    "import aeroolib",
    "import genshi",
    "from genshi.template import NewTextTemplate",
    "from xml.dom import minidom",
    "from pyPdf import PdfFileWriter, PdfFileReader",
]

# from . import check_deps
# check_deps(check_list)
