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

from math import sin, cos, pi, sqrt
from copy import deepcopy

#for dumps
from inspect import getmembers
from pprint import pprint

import dxf2gcode.globals.globals as g

from dxf2gcode.core.linegeo import LineGeo
from dxf2gcode.core.arcgeo import ArcGeo
from dxf2gcode.core.point import Point
from dxf2gcode.core.intersect import Intersect
from dxf2gcode.core.shape import Geos
from dxf2gcode.core.shape import Shape
from dxf2gcode.core.pocketmill import PocketMill
from dxf2gcode.core.shapeoffset import *

import logging
logger = logging.getLogger('core.stmove')


class StMove(object):
    """
    This Function generates the StartMove for each shape. It
    also performs the Plotting and Export of this moves. It is linked
    to the shape of its parent
    """
    # only need default arguments here because of the change of usage with super in QGraphicsLineItem
    def __init__(self, shape=None):
        if shape is None:
            return

        self.shape = shape

        self.updateShape()

    def __repr__(self):
        return "StMove(shape %d start %s angle %s end %s)" % \
            (self.shape.nr, str(self.start), str(self.angle), str(self.end))

    def append(self, geo):
        # we don't want to additional scale / rotate the stmove geo
        # so no geo.make_abs_geo(self.shape.parentEntity)
        geo.make_abs_geo()
        self.geos.append(geo)

    def updateShape(self):
        """
        Update start move after shape is changed.
        """
        self.start, self.angle = self.shape.get_start_end_points(True, True)
        self.end = self.start

        self.geos = Geos([])
        logging.debug("Updating the Start Move / Offset Geometry")
        self.make_start_moves()
        


    def make_start_moves(self):
        """
        This function called to create the start move. It will
        be generated based on the given values for start and angle.
        """
        self.geos = Geos([])

        if g.config.machine_type == 'drag_knife':
            self.make_swivelknife_move()
            return

        # Get the start rad. and the length of the line segment at begin.
        start_rad = self.shape.parentLayer.start_radius

        # Get tool radius based on tool diameter.
        tool_rad = self.shape.parentLayer.getToolRadius()

        # Calculate the starting point with and without compensation.
        start = self.start
        angle = self.angle

        ### drill cutted from here

        if self.shape.Drill == True:
            if isinstance(self.shape.geos[0], ArcGeo):
                start = self.shape.geos[0].abs_geo.O

            self.append(RapidPos(start))

            Ps_ein = start.get_arc_point(0,  tool_rad)

            # generate the start rad. and append it.
            circle = ArcGeo(Ps=Ps_ein, Pe=Ps_ein, O=start,
                               r=tool_rad, direction=1)

            self.append(circle)


        elif self.shape.cut_cor == 40:
            #if self.shape.Pocket == False:
            self.append(RapidPos(start))

        elif self.shape.cut_cor != 40 and not g.config.vars.Cutter_Compensation["done_by_machine"]:
            
            logging.debug("We have custom offset by tool")

            toolwidth = self.shape.parentLayer.getToolRadius()

            if self.shape.cut_cor == 41 and self.shape.cw is True:
                offtype = "out"
            elif self.shape.cut_cor == 41 and self.shape.cw is False:
                offtype = "in"
            elif self.shape.cut_cor == 42 and self.shape.cw is False:
                offtype = "out"
            elif self.shape.cut_cor == 42 and self.shape.cw is True:
                offtype = "in"
            else:
                offtype = "out"
                Warning("should not be here")
            logger.debug("Shape.cw %s; shape.cut_cor %i; Offset in direction: %s" %(self.shape.cw, self.shape.cut_cor,offtype))

            offshape = offShapeClass(parent = self.shape, offset = toolwidth, offtype = offtype)

            if len(offshape.rawoff) > 0:
                start, angle = offshape.rawoff[0].get_start_end_points(True, True)

                self.append(RapidPos(start))
                self.geos += offshape.rawoff

        # Cutting Compensation Left
        elif self.shape.cut_cor == 41:
            # Center of the Starting Radius.
            Oein = start.get_arc_point(angle + pi/2, start_rad + tool_rad)
            # Start Point of the Radius
            Ps_ein = Oein.get_arc_point(angle + pi, start_rad + tool_rad)
            # Start Point of the straight line segment at begin.
            Pg_ein = Ps_ein.get_arc_point(angle + pi/2, start_rad)

            # Get the dive point for the starting contour and append it.
            start_ein = Pg_ein.get_arc_point(angle, tool_rad)
            self.append(RapidPos(start_ein))

            # generate the Start Line and append it including the compensation.
            start_line = LineGeo(start_ein, Ps_ein)
            self.append(start_line)

            # generate the start rad. and append it.
            start_rad = ArcGeo(Ps=Ps_ein, Pe=start, O=Oein,
                               r=start_rad + tool_rad, direction=1)
            self.append(start_rad)

        # Cutting Compensation Right
        elif self.shape.cut_cor == 42:
            # Center of the Starting Radius.
            Oein = start.get_arc_point(angle - pi/2, start_rad + tool_rad)
            # Start Point of the Radius
            Ps_ein = Oein.get_arc_point(angle + pi, start_rad + tool_rad)
            # Start Point of the straight line segment at begin.
            Pg_ein = Ps_ein.get_arc_point(angle - pi/2, start_rad)

            # Get the dive point for the starting contour and append it.
            start_ein = Pg_ein.get_arc_point(angle, tool_rad)
            self.append(RapidPos(start_ein))

            # generate the Start Line and append it including the compensation.
            start_line = LineGeo(start_ein, Ps_ein)
            self.append(start_line)

            # generate the start rad. and append it.
            start_rad = ArcGeo(Ps=Ps_ein, Pe=start, O=Oein,
                               r=start_rad + tool_rad, direction=0)
            self.append(start_rad)
            
        # Pocket Milling - draw toolpath
        if self.shape.Pocket == True:
            
            pocket = PocketMill(self)
            pocket.createLines()
            
    def make_swivelknife_move(self):
        """
        Set these variables for your tool and material
        @param offset: knife tip distance from tool centerline. The radius of the
        tool is used for this.
        """
        offset = self.shape.parentLayer.getToolRadius()
        drag_angle = self.shape.drag_angle

        startnorm = offset*Point(1, 0)  # TODO make knife direction a config setting
        prvend, prvnorm = Point(), Point()
        first = True

        for geo in self.shape.geos.abs_iter():
            if isinstance(geo, LineGeo):
                geo_b = deepcopy(geo)
                if first:
                    first = False
                    prvend = geo_b.Ps + startnorm
                    prvnorm = startnorm
                norm = offset * (geo_b.Pe - geo_b.Ps).unit_vector()
                geo_b.Ps += norm
                geo_b.Pe += norm
                if not prvnorm == norm:
                    direction = prvnorm.to3D().cross_product(norm.to3D()).z
                    swivel = ArcGeo(Ps=prvend, Pe=geo_b.Ps, r=offset, direction=direction)
                    swivel.drag = drag_angle < abs(swivel.ext)
                    logger.debug(swivel)
                    self.append(swivel)
                logger.debug(geo_b)
                self.append(geo_b)

                prvend = geo_b.Pe
                prvnorm = norm
            elif isinstance(geo, ArcGeo):
                geo_b = deepcopy(geo)
                if first:
                    first = False
                    prvend = geo_b.Ps + startnorm
                    prvnorm = startnorm
                if geo_b.ext > 0.0:
                    norma = offset*Point(cos(geo_b.s_ang+pi/2), sin(geo_b.s_ang+pi/2))
                    norme = Point(cos(geo_b.e_ang+pi/2), sin(geo_b.e_ang+pi/2))
                else:
                    norma = offset*Point(cos(geo_b.s_ang-pi/2), sin(geo_b.s_ang-pi/2))
                    norme = Point(cos(geo_b.e_ang-pi/2), sin(geo_b.e_ang-pi/2))
                geo_b.Ps += norma
                if norme.x > 0:
                    geo_b.Pe = Point(geo_b.Pe.x+offset/(sqrt(1+(norme.y/norme.x)**2)),
                                     geo_b.Pe.y+(offset*norme.y/norme.x)/(sqrt(1+(norme.y/norme.x)**2)))
                elif norme.x == 0:
                    geo_b.Pe = Point(geo_b.Pe.x,
                                     geo_b.Pe.y)
                else:
                    geo_b.Pe = Point(geo_b.Pe.x-offset/(sqrt(1+(norme.y/norme.x)**2)),
                                     geo_b.Pe.y-(offset*norme.y/norme.x)/(sqrt(1+(norme.y/norme.x)**2)))
                if prvnorm != norma:
                    direction = prvnorm.to3D().cross_product(norma.to3D()).z
                    swivel = ArcGeo(Ps=prvend, Pe=geo_b.Ps, r=offset, direction=direction)
                    swivel.drag = drag_angle < abs(swivel.ext)
                    logger.debug(swivel)
                    self.append(swivel)
                prvend = geo_b.Pe
                prvnorm = offset*norme
                if -pi < geo_b.ext < pi:
                    swivel = ArcGeo(Ps=geo_b.Ps, Pe=geo_b.Pe, r=sqrt(geo_b.r ** 2 + offset ** 2), direction=geo_b.ext)
                    logger.debug(swivel)
                    self.append(swivel)

                else:
                    geo_b = ArcGeo(Ps=geo_b.Ps, Pe=geo_b.Pe, r=sqrt(geo_b.r**2+offset**2), direction=-geo_b.ext)
                    geo_b.ext = -geo_b.ext
                    logger.debug(geo_b)
                    self.append(geo_b)
            # TODO support different geos, or disable them in the GUI
            # else:
            #     self.append(copy(geo))
        if not prvnorm == startnorm:
            direction = prvnorm.to3D().cross_product(startnorm.to3D()).z
            swivel = ArcGeo(Ps=prvend, Pe=prvend - prvnorm + startnorm, r=offset, direction=direction)
            swivel.drag = drag_angle < abs(swivel.ext)
            logger.debug(swivel)
            self.append(swivel)

        self.geos.insert(0, RapidPos(self.geos.abs_el(0).Ps))
        self.geos[0].make_abs_geo()


    def make_path(self, drawHorLine, drawVerLine):
        for geo in self.geos.abs_iter():
            drawVerLine(self.shape, geo.get_start_end_points(True))
            geo.make_path(self.shape, drawHorLine)
        if len(self.geos):
            drawVerLine(self.shape, geo.get_start_end_points(False))


class RapidPos(Point):
    def __init__(self, point):
        Point.__init__(self, point.x, point.y)
        self.abs_geo = None

    def get_start_end_points(self, start_point, angles=None):
        if angles is None:
            return self
        elif angles:
            return self, 0
        else:
            return self, Point(0, -1) if start_point else Point(0, -1)

    def make_abs_geo(self, parent=None):
        """
        Generates the absolute geometry based on itself and the parent. This
        is done for rotating and scaling purposes
        """
        self.abs_geo = RapidPos(self.rot_sca_abs(parent=parent))

    def make_path(self, caller, drawHorLine):
        pass

    def Write_GCode(self, PostPro):
        """
        Writes the GCODE for a rapid position.
        @param PostPro: The PostProcessor instance to be used
        @return: Returns the string to be written to a file.
        """
        return PostPro.rap_pos_xy(self)
