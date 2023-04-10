# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2015
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
from __future__ import division

from math import sqrt

class Point3D(object):
    __slots__ = ["x", "y", "z"]

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return 'Point3D(X %.3f Y %.3f Z %.3f)' % (self.x, self.y, self.z)

    def save_v1(self):
        return 'X -> %6.3f  Y -> %6.3f   Z -> %6.3f' % (self.x, self.y, self.z)

    def __eq__(self, other):
        return (-1e-12 < self.x - other.x < 1e-12) and\
               (-1e-12 < self.y - other.y < 1e-12) and\
               (-1e-12 < self.z - other.z < 1e-12)

    def __ne__(self, other):
        return not self == other

    def __neg__(self):
        return -1.0 * self

    def __add__(self, other):
        return Point3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __radd__(self, other):
        return Point3D(self.x + other, self.y + other, self.z + other)

    def __sub__(self, other):
        return self + -other

    def __mul__(self, other):
        # Calculate Scalar (dot) Product
        return self.x * other.x + self.y * other.y + self.z * other.z

    def __rmul__(self, other):
        return Point3D(self.x * other, self.y * other, self.z * other)

    def __truediv__(self, other):
        return Point3D(self.x / other, self.y / other, self.z / other)

    def cross_product(self, other):
        return Point3D(self.y * other.z - self.z * other.y,
                       self.z * other.x - self.x * other.z,
                       self.x * other.y - self.y * other.x)

    def unit_vector(self):
        return self / self.length()

    def length_squared(self):
        return self.x**2 + self.y**2 + self.z**2

    def length(self):
        return sqrt(self.length_squared())
