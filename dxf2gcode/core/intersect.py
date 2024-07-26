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

from dxf2gcode.core.linegeo import LineGeo
from dxf2gcode.core.arcgeo import ArcGeo
from dxf2gcode.core.point import Point


class Intersect(object):
    @staticmethod
    def get_intersection_point(prv_geo, geo):
        intersection = None
        if isinstance(prv_geo, LineGeo) and isinstance(geo, LineGeo):
            intersection = Intersect.line_line_intersection(prv_geo, geo)
        elif isinstance(prv_geo, LineGeo) and isinstance(geo, ArcGeo):
            intersection = Intersect.line_arc_intersection(prv_geo, geo, prv_geo.Pe)
        elif isinstance(prv_geo, ArcGeo) and isinstance(geo, LineGeo):
            intersection = Intersect.line_arc_intersection(geo, prv_geo, prv_geo.Pe)
        elif isinstance(prv_geo, ArcGeo) and isinstance(geo, ArcGeo):
            intersection = Intersect.arc_arc_intersection(geo, prv_geo, prv_geo.Pe)
        return intersection

    @staticmethod
    def point_belongs_to_line(point, line):
        linex = sorted([line.Ps.x, line.Pe.x])
        liney = sorted([line.Ps.y, line.Pe.y])
        return (linex[0] - 1e-8 <= point.x <= linex[1] + 1e-8 and
                liney[0] - 1e-8 <= point.y <= liney[1] + 1e-8)

    @staticmethod
    def point_belongs_to_arc(point, arc):
        ang = arc.dif_ang(arc.Ps, point, arc.ext)
        return (arc.ext + 1e-8 >= ang >= -1e-8 if arc.ext > 0 else
                arc.ext - 1e-8 <= ang <= 1e-8)

    @staticmethod
    def line_line_intersection(line1, line2):
        # based on
        # http://stackoverflow.com/questions/20677795/find-the-point-of-intersecting-lines
        xydiff1 = line1.Ps - line1.Pe
        xydiff2 = line2.Ps - line2.Pe
        xdiff = (xydiff1.x, xydiff2.x)
        ydiff = (xydiff1.y, xydiff2.y)

        det = lambda a, b: a[0] * b[1] - a[1] * b[0]

        div = det(xdiff, ydiff)
        if div != 0:
            d = (det((line1.Ps.x, line1.Ps.y), (line1.Pe.x, line1.Pe.y)),
                 det((line2.Ps.x, line2.Ps.y), (line2.Pe.x, line2.Pe.y)))

            point = Point(det(d, xdiff) / div,
                              det(d, ydiff) / div)

            if Intersect.point_belongs_to_line(point, line1) and Intersect.point_belongs_to_line(point, line2):
                return point
        return None

    @staticmethod
    def line_arc_intersection(line, arc, refpoint):
        # based on
        # http://stackoverflow.com/questions/13053061/circle-line-intersection-points
        baX = line.Pe.x - line.Ps.x
        baY = line.Pe.y - line.Ps.y
        caX = arc.O.x - line.Ps.x
        caY = arc.O.y - line.Ps.y

        a = baX * baX + baY * baY
        bBy2 = baX * caX + baY * caY
        c = caX * caX + caY * caY - arc.r * arc.r

        if a == 0:
            return None

        pBy2 = bBy2 / a
        q = c / a

        disc = pBy2 * pBy2 - q
        if disc > 0:
            tmpSqrt = sqrt(disc)
            abScalingFactor1 = -pBy2 + tmpSqrt
            abScalingFactor2 = -pBy2 - tmpSqrt

            p1 = Point(line.Ps.x - baX * abScalingFactor1,
                       line.Ps.y - baY * abScalingFactor1)
            p2 = Point(line.Ps.x - baX * abScalingFactor2,
                       line.Ps.y - baY * abScalingFactor2)

            intersections = []
            if Intersect.point_belongs_to_arc(p1, arc) and Intersect.point_belongs_to_line(p1, line):
                intersections.append(p1)
            if Intersect.point_belongs_to_arc(p2, arc) and Intersect.point_belongs_to_line(p2, line):
                intersections.append(p2)
            intersections.sort(key=lambda x: (refpoint - x).length_squared())
            if len(intersections) > 0:
                return intersections[0]
        return None

    @staticmethod
    def arc_arc_intersection(arc1, arc2, refpoint):
        # based on
        # http://stackoverflow.com/questions/3349125/circle-circle-intersection-points
        d = arc1.O.distance(arc2.O)

        if d > (arc1.r + arc2.r):  # there are no solutions, the circles are separate
            return None
        elif d + 1e-5 < abs(arc1.r - arc2.r):  # there are no solutions because one circle is contained within the other
            return None
        elif d == 0:  # then the circles are coincident and there are an infinite number of solutions
            return None
        else:
            a = (arc1.r**2 - arc2.r**2 + d**2) / (2 * d)
            if arc1.r**2 - a**2 < 0:
                return None
            h = sqrt(arc1.r**2 - a**2)
            P2 = arc1.O + a * (arc2.O - arc1.O) / d

            p1 = Point(P2.x + h * (arc2.O.y - arc1.O.y) / d,
                       P2.y - h * (arc2.O.x - arc1.O.x) / d)
            p2 = Point(P2.x - h * (arc2.O.y - arc1.O.y) / d,
                       P2.y + h * (arc2.O.x - arc1.O.x) / d)

            intersections = []
            if Intersect.point_belongs_to_arc(p1, arc1) and Intersect.point_belongs_to_arc(p1, arc2):
                intersections.append(p1)
            if Intersect.point_belongs_to_arc(p2, arc1) and Intersect.point_belongs_to_arc(p2, arc2):
                intersections.append(p2)
            intersections.sort(key=lambda x: (refpoint - x).length_squared())
            if len(intersections) > 0:
                return intersections[0]
            return None
