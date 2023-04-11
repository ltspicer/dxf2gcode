# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2010-2015
#    Christian Kohlöffel
#    Jean-Paul Schouwstra
#
#   This file is part of DXF2GCODE.
#
#   DXF2GCODE is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   DXF2GCODE is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with DXF2GCODE.  If not, see <http://www.gnu.org/licenses/>.
#
############################################################################

"""
All global constants are initialized in this module.
They are used in the other modules.

see http://code.activestate.com/recipes/65207/ for module const

@purpose:  initialization of the global constants used within the other modules.
"""

import logging
import platform

from PyQt5 import QtCore

# Global Variables
APPNAME = "DXF2GCODE"
VERSION = "Py%s PyQt%s" % (platform.python_version(), QtCore.PYQT_VERSION_STR)

DATE     =  "$Date: Mon Feb 6 21:49:45 2023 +0100 $"
REVISION =  "$Revision: 179784cf9099b6439ed2d42b544ff77e805d02fb $"
AUTHOR   = u"$Author: christi_ko <christian.kohloeffel@googlemail.com> $"

CONFIG_EXTENSION = '.cfg'
PY_EXTENSION = '.py'
PROJECT_EXTENSION = '.d2g'

# Rename unreadable config/varspace files to .bad
BAD_CONFIG_EXTENSION = '.bad'
DEFAULT_CONFIG_DIR = 'config'
DEFAULT_POSTPRO_DIR = 'postpro_config'

# log related
DEFAULT_LOGFILE = 'dxf2gcode.log'
STARTUP_LOGLEVEL = logging.DEBUG
# PRT = logging.INFO
