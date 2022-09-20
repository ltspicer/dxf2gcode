#!/usr/bin/env python3
# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2018
#    Damian Wrobel <dwrobel@ertelnet.rybnik.pl>
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

import os
import subprocess
import sys
import unittest
from pathlib import Path
from pathlib import PurePath


class TestDXF2Gcode(unittest.TestCase):
    pass


def make_test_function(description, dxf2gcode, in_file, out_file):
    def test(self):
        c = []
        c.append(sys.executable)
        c.append(dxf2gcode)
        c.append('--quiet')
        c.append('-e')
        c.append(out_file)
        c.append(in_file)
        print("\n\nExecuting {0}".format(c))
        rv = subprocess.call(c)
        self.assertEqual(rv, 0, description)
        dxf = Path(out_file + '.ngc')
        rv = dxf.is_file()
        self.assertEqual(rv, True, description)
        rv = dxf.stat().st_size > 0
        self.assertEqual(rv, True, description)
        dxf.unlink()

    return test


def run_tests():
    dxf2gcode = './dxf2gcode.py'
    in_dir_name = '../dxf'
    out_dir_name = '.'
    files = os.listdir(in_dir_name)

    for name in files:
        in_file = PurePath(name)

        if not (in_file.match('*.dxf') or in_file.match('*.DXF')):
            continue

        test_name = in_file.name
        test_func = make_test_function(test_name,
                                       dxf2gcode,
                                       os.path.join(in_dir_name, name),
                                       os.path.join(out_dir_name, name))
        setattr(TestDXF2Gcode, 'test_{0}'.format(test_name), test_func)
    unittest.main()


if __name__ == '__main__':
    run_tests()
