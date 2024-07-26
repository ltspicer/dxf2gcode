# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2015-2016
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

from __future__ import absolute_import

import dxf2gcode.globals.constants as c

str_encode = lambda string: string
str_decode = lambda string: string

qstr_encode = lambda string: str_encode(string)

'''
Following two functions are needed for Python3+, since it no longer supports these functions as is
'''
def toInt(text):
    try:
        value = (int(text), True)
    except ValueError:
        value = (0, False)
    return value


def toFloat(text):
    try:
        value = (float(text), True)
    except ValueError:
        value = (0.0, False)
    return value


def a2u(text):
    """
    Convert ASCII string with encoded chars like \ U + xxxx to Python Unicode strings.
    """
    cur = 0
    out = str()
    while cur < len(text):
        idx = text.find('\\U+', cur)
        if idx < 0:
            out += text[cur:]
            break

        out += text[cur:idx]
        for cur in range(idx + 3, len(text) + 1):
            if cur == len (text):
                break
            if "0123456789abcdefABCDEF".find(text[cur]) < 0:
                break

        if cur == idx + 3:
            # "\U+" without following digits; copy to output as-is
            out += text[idx:cur]
            continue

        out += chr(int(text[idx+3:cur], 16))

    return out
