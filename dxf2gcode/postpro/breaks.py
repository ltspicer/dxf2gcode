# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2014-2015
#    Robert Lichtenberger
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

from math import sqrt
import logging

from dxf2gcode.core.linegeo import LineGeo
from dxf2gcode.core.arcgeo import ArcGeo
from dxf2gcode.core.breakgeo import BreakGeo
from dxf2gcode.core.point import Point
from dxf2gcode.core.shape import Geos

import dxf2gcode.globals.constants as c
from PyQt5.QtCore import QLineF, QPointF

logger = logging.getLogger("PostPro.Breaks")


class Breaks(object):
    """
    The Breaks Class includes the functions for processing shapes on layers named BREAKS: to break closed shapes so that
    the resulting G-Code will contain rests for the workpiece.
    """
    def __init__(self, layerContents):
        self.layerContents = layerContents
        """
        Process layerContents: Each non-BREAKS: layers shapes are checked against all the shapes in all BREAKS: layers.
        If a shape is intersected twice by a break-shape, the shape will be broken.
        """
        self.breakLayers = []
        for layerContent in self.layerContents.break_layer_iter():
            self.breakLayers.append(layerContent)

        logger.debug("Found %d break layers" % len(self.breakLayers))

    def getNewGeos(self, geos):
        # TODO use intersect class and update_start_end_points
        new_geos = Geos([])
        for geo in geos.abs_iter():
            if isinstance(geo, LineGeo):
                new_geos.extend(self.breakLineGeo(geo))
            elif isinstance(geo, ArcGeo):
                new_geos.extend(self.breakArcGeo(geo))
            else:
                new_geos.append(geo)
        return new_geos

    def breakLineGeo(self, lineGeo):
        """
        Try to break passed lineGeo with any of the shapes on a break layers.
        Will break lineGeos recursively.
        @return: The list of geometries after breaking (lineGeo itself if no breaking happened)
        """
        newGeos = Geos([])
        for breakLayer in self.breakLayers:
            for breakShape in breakLayer.shapes.not_disabled_iter():
                intersections = self.intersectLineGeometry(lineGeo, breakShape)
                if len(intersections) == 2:
                    (near, far) = self.classifyIntersections(lineGeo, intersections)
                    logger.debug("Line %s broken from (%f, %f) to (%f, %f)" % (lineGeo.to_short_string(), near.x, near.y, far.x, far.y))
                    newGeos.extend(self.breakLineGeo(LineGeo(lineGeo.Ps, near)))
                    newGeos.append(BreakGeo(near, far, breakShape.axis3_mill_depth, breakShape.f_g1_plane, breakShape.f_g1_depth))
                    newGeos.extend(self.breakLineGeo(LineGeo(far, lineGeo.Pe)))
                    return newGeos
        return [lineGeo]

    def breakArcGeo(self, arcGeo):
        """
        Try to break passed arcGeo with any of the shapes on a break layers.
        Will break arcGeos recursively.
        @return: The list of geometries after breaking (arcGeo itself if no breaking happened)
        """
        newGeos = Geos([])
        for breakLayer in self.breakLayers:
            for breakShape in breakLayer.shapes.not_disabled_iter():
                intersections = self.intersectArcGeometry(arcGeo, breakShape)
                if len(intersections) == 2:
                    (near, far) = self.classifyIntersections(arcGeo, intersections)
                    logger.debug("Arc %s broken from (%f, %f) to (%f, %f)" % (arcGeo.toShortString(), near.x, near.y, far.x, far.y))
                    newGeos.extend(self.breakArcGeo(ArcGeo(Ps=arcGeo.Ps, Pe=near, O=arcGeo.O, r=arcGeo.r, s_ang=arcGeo.s_ang, direction=arcGeo.ext)))
                    newGeos.append(BreakGeo(near, far, breakShape.axis3_mill_depth, breakShape.f_g1_plane, breakShape.f_g1_depth))
                    newGeos.extend(self.breakArcGeo(ArcGeo(Ps=far, Pe=arcGeo.Pe, O=arcGeo.O, r=arcGeo.r, e_ang=arcGeo.e_ang, direction=arcGeo.ext)))
                    return newGeos
        return [arcGeo]

    def intersectLineGeometry(self, lineGeo, breakShape):
        """
        Try to break lineGeo with the given breakShape. Will return the intersection points of lineGeo with breakShape.
        """
        # TODO geos should be abs
        intersections = []
        line = QLineF(lineGeo.Ps.x, lineGeo.Ps.y, lineGeo.Pe.x, lineGeo.Pe.y)
        for breakGeo in breakShape.geos.abs_iter():
            if isinstance(breakGeo, LineGeo):
                breakLine = QLineF(breakGeo.Ps.x, breakGeo.Ps.y, breakGeo.Pe.x, breakGeo.Pe.y)
                intersection = QPointF(0, 0)  # values do not matter
                res = line.intersect(breakLine, intersection)
                if res == QLineF.BoundedIntersection:
                    intersections.append(Point(intersection.x(), intersection.y()))
        return intersections

    def intersectArcGeometry(self, arcGeo, breakShape):
        """
        Get the intersections between the finite line and arc.
        Algorithm based on http://vvvv.org/contribution/2d-circle-line-intersections
        """
        # TODO geos should be abs
        intersections = []
        for breakGeo in breakShape.geos.abs_iter():
            if isinstance(breakGeo, LineGeo):
                dxy = breakGeo.Pe - breakGeo.Ps
                a = dxy.x**2 + dxy.y**2
                b = 2 * (dxy.x * (breakGeo.Ps.x - arcGeo.O.x) + dxy.y * (breakGeo.Ps.y - arcGeo.O.y))
                c = breakGeo.Ps.x**2 + breakGeo.Ps.y**2 + arcGeo.O.x**2 + arcGeo.O.y**2\
                    - 2 * (arcGeo.O.x * breakGeo.Ps.x + arcGeo.O.y * breakGeo.Ps.y)\
                    - arcGeo.r**2
                bb4ac = b * b - 4 * a * c

                if bb4ac > 0:
                    mu1 = (-b + sqrt(bb4ac)) / (2*a)
                    mu2 = (-b - sqrt(bb4ac)) / (2*a)
                    p1 = breakGeo.Ps + mu1 * dxy
                    p2 = breakGeo.Ps + mu2 * dxy

                    # Points belong to the finite line?
                    if not\
                        (p1.x < breakGeo.Ps.x and p2.x < breakGeo.Ps.x and p1.x < breakGeo.Pe.x and p2.x < breakGeo.Pe.x or
                         p1.y < breakGeo.Ps.y and p2.y < breakGeo.Ps.y and p1.y < breakGeo.Pe.y and p2.y < breakGeo.Pe.y or
                         p1.x > breakGeo.Ps.x and p2.x > breakGeo.Ps.x and p1.x > breakGeo.Pe.x and p2.x > breakGeo.Pe.x or
                         p1.y > breakGeo.Ps.y and p2.y > breakGeo.Ps.y and p1.y > breakGeo.Pe.y and p2.y > breakGeo.Pe.y):

                        if arcGeo.O.distance(breakGeo.Ps) >= arcGeo.r and self.point_belongs_to_arc(p2, arcGeo):
                            intersections.append(p2)
                        if arcGeo.O.distance(breakGeo.Pe) >= arcGeo.r and self.point_belongs_to_arc(p1, arcGeo):
                            intersections.append(p1)
        return intersections

    def point_belongs_to_arc(self, point, arcGeo):
        ang = arcGeo.dif_ang(arcGeo.Ps, point, arcGeo.ext)
        return arcGeo.ext >= ang > 0 if arcGeo.ext > 0 else arcGeo.ext <= ang < 0

    def classifyIntersections(self, geo, intersection):
        """
        Investigate the array intersection (which contains exactly two Point instances) and return (near, far) tuple, depending on the distance of the points to the start point of the geometry geo.
        """
        if geo.Ps.distance(intersection[0]) < geo.Ps.distance(intersection[1]):
            return (intersection[0], intersection[1])
        else:
            return (intersection[1], intersection[0])
