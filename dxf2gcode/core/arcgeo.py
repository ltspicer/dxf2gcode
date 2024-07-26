# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2008-2015
#    Christian Kohlöffel
#    Vinzenz Schulz
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

from math import sqrt, sin, cos, asin, pi, degrees, ceil, floor
from copy import deepcopy


from dxf2gcode.core.point import Point

from dxf2gcode.core.boundingbox import BoundingBox
import dxf2gcode.globals.globals as g

import dxf2gcode.globals.constants as c
from PyQt5 import QtCore

import logging
logger = logging.getLogger("core.arcgeo")

eps = 1e-12


class ArcGeo(object):

    """
    Standard Geometry Item used for DXF Import of all geometries, plotting and
    G-Code export.
    """

    def __init__(self, Ps=None, Pe=None, O=None, r=1,
                 s_ang=None, e_ang=None, direction=1, drag=False):
        """
        Standard Method to initialize the ArcGeo. Not all of the parameters are
        required to fully define a arc. e.g. Ps and Pe may be given or s_ang and
        e_ang
        @param Ps: The Start Point of the arc
        @param Pe: the End Point of the arc
        @param O: The center of the arc
        @param r: The radius of the arc
        @param s_ang: The Start Angle of the arc
        @param e_ang: the End Angle of the arc
        @param direction: The arc direction where 1 is in positive direction
        """

        self.Ps = Ps
        self.Pe = Pe
        self.O = O
        self.r = abs(r)
        self.s_ang = s_ang
        self.e_ang = e_ang
        self.drag = drag

        # Get the Circle center point with known Start and End Points
        if self.O is None:

            if self.Ps is not None and\
               self.Pe is not None and\
               direction is not None:

                arc = self.Pe.norm_angle(self.Ps) - pi / 2
                m = self.Pe.distance(self.Ps) / 2

                if abs(self.r - m) < g.config.fitting_tolerance:
                    lo = 0.0
                else:
                    lo = sqrt(pow(self.r, 2) - pow(m, 2))

                d = -1 if direction < 0 else 1

                self.O = self.Ps + (self.Pe - self.Ps) / 2
                self.O.y += lo * sin(arc) * d
                self.O.x += lo * cos(arc) * d

            # Compute center point
            elif self.s_ang is not None:
                self.O.x = self.Ps.x - self.r * cos(self.s_ang)
                self.O.y = self.Ps.y - self.r * sin(self.s_ang)
            else:
                logger.error(self.tr("Missing value for Arc Geometry"))
        else:
            self.r = self.O.distance(self.Ps)

        # Calculate start and end angles
        if self.s_ang is None:
            self.s_ang = self.O.norm_angle(self.Ps)
        if self.e_ang is None:
            self.e_ang = self.O.norm_angle(self.Pe)

        self.ext = self.dif_ang(self.Ps, self.Pe, direction)

        self.length = self.r * abs(self.ext)

        self.calc_bounding_box()

        self.abs_geo = None

    def __deepcopy__(self, memo):
        return ArcGeo(deepcopy(self.Ps, memo),
                      deepcopy(self.Pe, memo),
                      deepcopy(self.O, memo),
                      deepcopy(self.r, memo),
                      deepcopy(self.s_ang, memo),
                      deepcopy(self.e_ang, memo),
                      deepcopy(self.ext, memo),
                      deepcopy(self.drag, memo))

    def __repr__(self):
        """
        Standard method to print the object
        @return: A string
        """
        return ("ArcGeo (Ps=%s, Pe=%s, O=%s, s_ang=%s, e_ang=%s, r=%s, ext=%s)" % \
                (self.Ps, self.Pe, self.O, self.s_ang, self.e_ang, self.r, self.ext))

    def save_v1(self):
        return "\nArcGeo" +\
               "\nPs:  %s; s_ang: %0.5f" % (self.Ps.save_v1(), self.s_ang) +\
               "\nPe:  %s; e_ang: %0.5f" % (self.Pe.save_v1(), self.e_ang) +\
               "\nO:   %s; r: %0.3f" % (self.O.save_v1(), self.r) +\
               "\next: %0.5f; length: %0.5f" % (self.ext, self.length)

    def angle_between(self, min_ang, max_ang, angle):
        """
        Returns if the angle is in the range between 2 other angles
        @param min_ang: The starting angle
        @param parent: The end angel. Always in ccw direction from min_ang
        @return: True or False
        """
        if min_ang < 0.0:
            min_ang += 2 * pi

        while max_ang < min_ang:
            max_ang += 2 * pi

        while angle < min_ang:
            angle += 2 * pi

        return (min_ang < angle) and (angle <= max_ang)

    def calc_bounding_box(self):
        """
        Calculated the BoundingBox of the geometry and saves it into self.BB
        """

        Ps = Point(x=self.O.x - self.r, y=self.O.y - self.r)
        Pe = Point(x=self.O.x + self.r, y=self.O.y + self.r)

        # Do the calculation only for arcs have positiv extend => switch angles
        if self.ext >= 0:
            s_ang = self.s_ang
            e_ang = self.e_ang
        elif self.ext < 0:
            s_ang = self.e_ang
            e_ang = self.s_ang

        # If the positive X Axis is crossed
        if not(self.wrap(s_ang, 0) >= self.wrap(e_ang, 1)):
            Pe.x = max(self.Ps.x, self.Pe.x)

        # If the positive Y Axis is crossed
        if not(self.wrap(s_ang - pi / 2, 0) >= self.wrap(e_ang - pi / 2, 1)):
            Pe.y = max(self.Ps.y, self.Pe.y)

        # If the negative X Axis is crossed
        if not(self.wrap(s_ang - pi, 0) >= self.wrap(e_ang - pi, 1)):
            Ps.x = min(self.Ps.x, self.Pe.x)

        # If the negative Y is crossed
        if not(self.wrap(s_ang - 1.5 * pi, 0) >=
                self.wrap(e_ang - 1.5 * pi, 1)):
            Ps.y = min(self.Ps.y, self.Pe.y)

        self.BB = BoundingBox(Ps=Ps, Pe=Pe)

    def dif_ang(self, Ps, Pe, direction):
        """
        Calculated the angle between Pe and Ps with respect to the origin
        @param Ps: the start Point of the arc
        @param Pe: the end Point of the arc
        @param direction: the direction of the arc
        @return: Returns the angle between -2*pi and 2*pi for the arc,
        0 excluded - we got a complete circle
        """
        dif_ang = (self.O.norm_angle(Pe) - self.O.norm_angle(Ps)) % (-2 * pi)

        if direction > 0:
            dif_ang += 2 * pi
        elif dif_ang == 0:
            dif_ang = -2 * pi

        return dif_ang

    def get_point_from_start(self, i, segments):
        """
        Returns an point on the end point of the segments on the arc.
        @param i: The end point of the segements which shall be returned
        @param segment: The number of segments into which the arc shall be diffided.
        @return: Returns a point on the Arc.
        """
        ang = self.s_ang + i * self.ext / segments
        return self.O.get_arc_point(ang, self.r)

    def get_start_end_points(self, start_point, angles=None):
        if start_point:
            if angles is None:
                return self.Ps
            elif angles:
                return self.Ps, self.s_ang + pi / 2 * self.ext / abs(self.ext)
            else:
                direction = (self.O - self.Ps).unit_vector()
                direction = -direction if self.ext >= 0 else direction
                return self.Ps, Point(-direction.y, direction.x)
        else:
            if angles is None:
                return self.Pe
            elif angles:
                return self.Pe, self.e_ang - pi / 2 * self.ext / abs(self.ext)
            else:
                direction = (self.O - self.Pe).unit_vector()
                direction = -direction if self.ext >= 0 else direction
                return self.Pe, Point(-direction.y, direction.x)

    def distance_a_p(self, other):
        """
        Find the distance between a arc and a point
        @param other: the instance of the 2nd geometry element.
        @return: The distance between the two geometries
        """
        # The Pont is outside of the Arc
        if self.O.distance(other) > self.r:
            # If the Nearest Point is on Arc Segement it is the neares one.
            # logger.debug("Nearest Point is outside of arc")
            if self.PointAng_withinArc(other):
                return other.distance(self.O.get_arc_point(self.O.norm_angle(other), r=self.r))
            elif other.distance(self.Ps) < other.distance(self.Pe):
                return other.distance(self.Ps)
            else:
                return other.distance(self.Pe)

        # logger.debug("Nearest Point is Inside of arc")
        # logger.debug("self.distance(other.Ps): %s, self.distance(other.Pe): %s" %(self.distance(other.Ps),self.distance(other.Pe)))
        # The Line may be inside of the ARc or cross it
        if other.distance(self.Ps) < other.distance(self.Pe):
            dis_min = other.distance(self.Ps)
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))
        else:
            dis_min = other.distance(self.Pe)
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))

        if ((self.PointAng_withinArc(other)) and
                abs(self.r - self.O.distance(other)) < dis_min):
            dis_min = abs(self.r - self.O.distance(other))
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))

        return dis_min

    def PointAng_withinArc(self, Point):
        """
        Check if the angle defined by Point is within the span of the arc.
        @param Point: The Point which angle to be checked
        @return: True or False
        """
        if self.ext == 0.0:
            return False

        v = self.dif_ang(self.Ps, Point, self.ext) / self.ext
        return v >= 0.0 and v <= 1.0

    def isHit(self, caller, xy, tol):
        """
        This function returns true if the nearest point between the two geometries is within the square of the
        given tolerance
        @param caller: This is the calling entities (only used in holegeo)
        @param xy: The point which shall be used to determine the distance
        @tol: The tolerance which is used for Hit testing.
        """
        return self.distance_a_p(xy) <= tol

    def make_abs_geo(self, parent=None):
        """
        Generates the absolute geometry based on itself and the parent. This
        is done for rotating and scaling purposes
        """
        Ps = self.Ps.rot_sca_abs(parent=parent)
        Pe = self.Pe.rot_sca_abs(parent=parent)
        O = self.O.rot_sca_abs(parent=parent)
        r = self.scaled_r(self.r, parent)

        direction = 1 if self.ext > 0.0 else -1

        #TODO this might cause problem for recursive loops
        if parent is not None and parent.sca[0] * parent.sca[1] < 0.0:
           direction *= -1

        if not(parent==None):
            while not(parent.parent==None):
                parent=parent.parent

            if (not (parent.mirrorx and parent.mirrory)) and (parent.mirrorx or parent.mirrory):
                direction *= -1

        self.abs_geo = ArcGeo(Ps=Ps, Pe=Pe, O=O, r=r, direction=direction, drag=self.drag)

    def make_path(self, caller, drawHorLine):
        segments = int(abs(degrees(self.ext)) // 3 + 1)
        Ps = self.O.get_arc_point(self.s_ang, self.r)

        for i in range(1, segments + 1):
            Pe = self.get_point_from_start(i, segments)
            drawHorLine(caller, Ps, Pe)
            Ps = Pe

    def reverse(self):
        """
        Reverses the direction of the arc (switch direction).
        """
        self.Ps, self.Pe = self.Pe, self.Ps
        self.s_ang, self.e_ang = self.e_ang, self.s_ang
        self.ext = -self.ext
        if self.abs_geo:
            self.abs_geo.reverse()

    def scaled_r(self, r, parent):
        """
        Scales the radius based on the scale given in its parents. This is done
        recursively.
        @param r: The radius which shall be scaled
        @param parent: The parent Entity (Instance: EntityContentClass)
        @return: The scaled radius
        """
        # Rekursive Schleife falls mehrfach verschachtelt.
        # Recursive loop if nested.
        if parent is not None:
            r *= parent.sca[0]
            r = self.scaled_r(r, parent.parent)

        return r

    def toShortString(self):
        return "(%f, %f) -> (%f, %f)" % (self.Ps.x, self.Ps.y, self.Pe.x, self.Pe.y)

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QtCore.QCoreApplication.translate('ArcGeo',
                                                           string_to_translate))

    def update_start_end_points(self, start_point, value):
        prv_dir = self.ext
        if start_point:
            self.Ps = value
            self.s_ang = self.O.norm_angle(self.Ps)
        else:
            self.Pe = value
            self.e_ang = self.O.norm_angle(self.Pe)

        self.ext = self.dif_ang(self.Ps, self.Pe, self.ext)

        if 2 * abs(((prv_dir - self.ext) + pi) % (2 * pi) - pi) >= pi:
            # seems very unlikely that this is what you want - the direction
            # changed (too drastically)
            self.Ps, self.Pe = self.Pe, self.Ps
            self.s_ang, self.e_ang = self.e_ang, self.s_ang
            self.ext = self.dif_ang(self.Ps, self.Pe, prv_dir)

        self.length = self.r * abs(self.ext)

    def wrap(self, angle, isend=0):
        """
        Wrapes the given angle into a range between 0 and 2pi
        @param angle: The angle to be wraped
        @param isend: If the angle is the end angle or start angle, this makes a
        difference at 0 or 2pi.
        @return: Returns the angle between 0 and 2 *pi
        """
        wrap_angle = angle % (2 * pi)
        if isend and wrap_angle == 0.0:
            wrap_angle += 2 * pi
        elif wrap_angle == 2 * pi:
            wrap_angle -= 2 * pi

        return wrap_angle

    def Write_GCode(self, PostPro=None):
        """
        Writes the GCODE for an Arc.
        @param PostPro: The PostProcessor instance to be used
        @return: Returns the string to be written to a file.
        """
        Ps, s_ang = self.get_start_end_points(True, True)
        Pe, e_ang = self.get_start_end_points(False, True)

        O = self.O
        r = self.r
        IJ = O - Ps

        # If the radius of the element is bigger than the max, radius export
        # the element as an line.
        if r > PostPro.vars.General["max_arc_radius"]:
            string = PostPro.lin_pol_xy(Ps, Pe)
        # If the maschine is not supporting G2 and G3 moves use this option

        elif PostPro.vars.General["export_arcs_as_lines"]:
            # Calculation the min. arc segment angle of the export based on given tolerance.
            # https://de.wikipedia.org/wiki/Kreissegment
            a = g.config.fitting_tolerance
            s = 2 * sqrt(a * (2 * self.r - a))
            alpha = 2 * asin(s / (2 * self.r))
            segments = int(abs(self.ext // alpha))

            string = ""

            for i in range(1, segments + 1):
                Pe = self.get_point_from_start(i, segments)
                string += PostPro.lin_pol_xy(Ps, Pe)
                Ps = Pe
        else:
            if self.ext > 0:
                string = PostPro.lin_pol_arc(
                    "ccw", Ps, Pe, s_ang, e_ang, r, O, IJ, self.ext)
            elif self.ext < 0 and PostPro.vars.General["export_ccw_arcs_only"]:
                string = PostPro.lin_pol_arc(
                    "ccw", Pe, Ps, e_ang, s_ang, r, O, O - Pe, self.ext)
            else:
                string = PostPro.lin_pol_arc(
                    "cw", Ps, Pe, s_ang, e_ang, r, O, IJ, self.ext)
        return string
