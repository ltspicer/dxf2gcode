# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2008-2015
#    Christian Kohlöffel
#    Vinzenz Schulz
#    Jean-Paul Schouwstra
#
#   Copyright (C) 20019-2020
#    San Zamoyski
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

from __future__ import division

#from math import sqrt, pi
#from copy import deepcopy

from dxf2gcode.core.point import Point
#from dxf2gcode.core.boundingbox import BoundingBox
#from dxf2gcode.core.arcgeo import ArcGeo

import logging
logger = logging.getLogger("core.pocketmove")

#eps = 1e-12

class PocketMove(object):

    """
    Non Standard Geometry Item used for moving over element, plotting and
    G-Code export. Generally for milling pockets.
    """

    def __init__(self, Ps, Pe):
        """
        Standard Method to initialize PocketMove.
        @param Ps: The Start Point of the line
        @param Pe: the End Point of the line
        """
        self.Ps = Ps
        self.Pe = Pe
        self.length = self.Ps.distance(self.Pe)

        #self.calc_bounding_box()

        self.abs_geo = None
        
        #This values will be set and used
        # while generating GCode
        self.feedZ = 0
        self.feedXY = 0
        self.safe = 0
        self.depth = 0
        self.retr = 0

    """
    def __deepcopy__(self, memo):
        return LineGeo(deepcopy(self.Ps, memo),
                       deepcopy(self.Pe, memo))
    """
    
    def __str__(self):
        """
        Standard method to print the object
        @return: A string
        """
        return ("PocketMove form %s x %s to %s x %s." (self.Ps.x, self.Ps.y, self.Pe.x, self.Pe.y))

    """
    def save_v1(self):
        return "\nLineGeo" +\
               "\nPs:     %s" % self.Ps.save_v1() +\
               "\nPe:     %s" % self.Pe.save_v1() +\
               "\nlength: %0.5f" % self.length
    """
    
    """
    def calc_bounding_box(self):
        \"""
        Calculated the BoundingBox of the geometry and saves it into self.BB
        \"""
        Ps = Point(x=min(self.Ps.x, self.Pe.x), y=min(self.Ps.y, self.Pe.y))
        Pe = Point(x=max(self.Ps.x, self.Pe.x), y=max(self.Ps.y, self.Pe.y))

        self.BB = BoundingBox(Ps=Ps, Pe=Pe)
    """
    
    #Function from RapidMove replaced with original from LineGeo
    def get_start_end_points(self, start_point, angles=None):
        if start_point:
            if angles is None:
                return self.Ps
            elif angles:
                return self.Ps, self.Ps.norm_angle(self.Pe)
            else:
                return self.Ps, (self.Pe - self.Ps).unit_vector()
        else:
            if angles is None:
                return self.Pe
            elif angles:
                return self.Pe, self.Pe.norm_angle(self.Ps)
            else:
                return self.Pe, (self.Pe - self.Ps).unit_vector()
            
    #Sets values for GCode generation
    def setZMove(self, feedz, feedxy, safe, depth, retr):
        self.feedZ = feedz
        self.feedXY = feedxy
        self.safe = safe
        self.depth = depth
        self.retr = retr
    
    """
    def distance_l_p(self, Point):
        \"""
        Find the shortest distance between CCLineGeo and Point elements.
        Algorithm acc. to
        http://notejot.com/2008/09/distance-from-Point-to-line-segment-in-2d/
        http://softsurfer.com/Archive/algorithm_0106/algorithm_0106.htm
        @param Point: the Point
        @return: The shortest distance between the Point and Line
        \"""
        d = self.Pe - self.Ps
        v = Point - self.Ps

        t = d.dotProd(v)

        if t <= 0:
            # our Point is lying "behind" the segment
            # so end Point 1 is closest to Point and distance is length of
            # vector from end Point 1 to Point.
            return self.Ps.distance(Point)
        elif t >= d.dotProd(d):
            # our Point is lying "ahead" of the segment
            # so end Point 2 is closest to Point and distance is length of
            # vector from end Point 2 to Point.
            return self.Pe.distance(Point)
        else:
            # our Point is lying "inside" the segment
            # i.e.:a perpendicular from it to the line that contains the line
            if (v.dotProd(v) - (t * t) / d.dotProd(d)) < eps:
                return 0.0
            else:
                return sqrt(v.dotProd(v) - (t * t) / d.dotProd(d))
    """
    
    """
    def isHit(self, caller, xy, tol):
        \"""
        This function returns true if the nearest point between the two geometries is within the square of the 
        given tolerance
        @param caller: This is the calling entities (only used in holegeo)
        @param xy: The point which shall be used to determine the distance
        @tol: The tolerance which is used for Hit testing.
        \"""
        return self.distance_l_p(xy) <= tol
    """
    
    #Function from RapidMove replaced with original from LineGeo (mod)
    def make_abs_geo(self, parent=None):
        """
        Generates the absolute geometry based on itself and the parent. This
        is done for rotating and scaling purposes
        """
        Ps = self.Ps.rot_sca_abs(parent=parent)
        Pe = self.Pe.rot_sca_abs(parent=parent)

        self.abs_geo = PocketMove(Ps=Ps, Pe=Pe)
    
    #Function from RapidMove replaced with original from LineGeo
    def make_path(self, caller, drawHorLine):
        drawHorLine(caller, self.Ps, self.Pe)
        
    """
    def reverse(self):
        \"""
        Reverses the direction of the arc (switch direction).
        \"""
        self.Ps, self.Pe = self.Pe, self.Ps
        if self.abs_geo:
            self.abs_geo.reverse()
    """
    
    """
    def to_short_string(self):
        return "(%f, %f) -> (%f, %f)" % (self.Ps.x, self.Ps.y, self.Pe.x, self.Pe.y)
    """

    """
    def update_start_end_points(self, start_point, value):
        prv_ang = self.Ps.norm_angle(self.Pe)
        if start_point:
            self.Ps = value
        else:
            self.Pe = value
        new_ang = self.Ps.norm_angle(self.Pe)

        if 2 * abs(((prv_ang - new_ang) + pi) % (2 * pi) - pi) >= pi:
            # seems very unlikely that this is what you want - the direction
            # changed (too drastically)
            self.Ps, self.Pe = self.Pe, self.Ps

        self.length = self.Ps.distance(self.Pe)
    """

    def Write_GCode(self, PostPro):
        exstr = ""
        """
        Writes the GCODE for a rapid position.
        @param PostPro: The PostProcessor instance to be used
        @return: Returns the string to be written to a file.
        """
        exstr += PostPro.chg_feed_rate(self.feedZ)
        exstr += PostPro.lin_pol_z(self.safe)
        exstr += PostPro.rap_pos_z(self.retr)
        
        exstr += PostPro.rap_pos_xy(self.Pe)
        
        #TODO: going Z-up can be done as full speed?
        exstr += PostPro.rap_pos_z(self.safe)
        exstr += PostPro.chg_feed_rate(self.feedZ)
        exstr += PostPro.lin_pol_z(self.depth)
        exstr += PostPro.chg_feed_rate(self.feedXY)
        
        return exstr

    """
    def Write_GCode(self, PostPro):
        \"""
        Writes the GCODE for a Line.
        @param PostPro: The PostProcessor instance to be used
        @return: Returns the string to be written to a file.
        \"""
        Ps = self.get_start_end_points(True)
        Pe = self.get_start_end_points(False)
        return PostPro.lin_pol_xy(Ps, Pe)
    """
