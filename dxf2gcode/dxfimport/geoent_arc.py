# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2008-2015
#    Christian Kohlöffel
#    Vinzenz Schulz
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

from math import sin, cos, radians, pi
import logging

from dxf2gcode.core.point import Point
from dxf2gcode.dxfimport.classes import PointsClass
from dxf2gcode.core.arcgeo import ArcGeo
from dxf2gcode.globals.helperfunctions import a2u

import dxf2gcode.globals.constants as c
from PyQt5 import QtCore

logger = logging.getLogger("DXFImport.GeoentArc")


class GeoentArc(object):
    def __init__(self, Nr=0, caller=None):
        self.Typ = 'Arc'
        self.Nr = Nr
        self.Layer_Nr = 0
        self.length = 0
        self.geo = []

        # Lesen der Geometrie
        # Read the geometry
        self.Read(caller)

    def __repr__(self):
        # how to print the object
        return "\nArc:" + \
               "\n\tNr: %i" % self.Nr + \
               "\n\tLayer Nr:%i" % self.Layer_Nr + \
               "\n\t" + str(self.geo[-1])

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QtCore.QCoreApplication.translate('GeoentArc',
                                                           string_to_translate))

    def App_Cont_or_Calc_IntPts(self, cont, points, i, tol):
        """
        App_Cont_or_Calc_IntPts()
        """
        if abs(self.length) <= tol:
            return False

        points.append(PointsClass(point_nr=len(points),
                                  geo_nr=i,
                                  Layer_Nr=self.Layer_Nr,
                                  be=self.geo[-1].Ps,
                                  en=self.geo[-1].Pe,
                                  be_cp=[], en_cp=[]))
        return True

    def Read(self, caller):
        """
        Read()
        """
        # Typically all Arc's are CCW
        extrusion_dir=1
        
        # Assign short name
        lp = caller.line_pairs
        e = lp.index_code(0, caller.start + 1)

        # Assign layer
        s = lp.index_code(8, caller.start + 1)
        self.Layer_Nr = caller.Get_Layer_Nr(a2u(lp.line_pair[s].value))

        # X Value
        s = lp.index_code(10, s + 1)
        x0 = float(lp.line_pair[s].value)

        # Y Value
        s = lp.index_code(20, s + 1)
        y0 = float(lp.line_pair[s].value)
     
        # Radius
        s = lp.index_code(40, s + 1)
        r = float(lp.line_pair[s].value)

        # Start angle
        s = lp.index_code(50, s + 1)
        s_ang = radians(float(lp.line_pair[s].value))

        # End angle
        s = lp.index_code(51, s + 1)
        e_ang = radians(float(lp.line_pair[s].value))

        # Searching for an extrusion direction
        s_nxt_xt = lp.index_code(230, caller.start + 1, e)
        # If there is a extrusion direction given flip around x-Axis
        if s_nxt_xt is not None:
            extrusion_dir = float(lp.line_pair[s_nxt_xt].value)
            logger.debug(self.tr('Found extrusion direction: %s') % extrusion_dir)
            logger.debug("x0: %s; s_ang: %s; e_ang: %s" % (x0,s_ang,e_ang))   
            if extrusion_dir == -1:
                x0 = -x0
                
                #https://de.bettermarks.com/mathe/trigonometrie-am-einheitskreis/
                if s_ang <= pi:
                    s_ang=pi-s_ang
                else:
                    s_ang=2*pi-(s_ang-pi)
                    
                if e_ang <= pi:
                    e_ang=pi-e_ang
                else:
                    e_ang=2*pi-(e_ang-pi)
                logger.debug("x0: %s; s_ang: %s; e_ang: %s" % (x0,s_ang,e_ang))                
                


        # Calculate the start and end points of the arcs
        O = Point(x0, y0)
        Ps = Point(cos(s_ang) * r, sin(s_ang) * r) + O
        Pe = Point(cos(e_ang) * r, sin(e_ang) * r) + O

        # Anh�ngen der ArcGeo Klasse f�r die Geometrie
        # Annexes to ArcGeo class for geometry
        self.geo.append(ArcGeo(Ps=Ps, Pe=Pe, O=O, r=r,
                               s_ang=s_ang, e_ang=e_ang, direction=extrusion_dir))

        # L�nge entspricht der L�nge des Kreises
        # Length is the length (circumference?) of the circle
        self.length = self.geo[-1].length

        #        logger.debug(self.geo[-1])

        # Neuen Startwerd f�r die n�chste Geometrie zur�ckgeben
        # New starting value for the next geometry
        caller.start = s
        
        logger.debug(self)

    def get_start_end_points(self, direction):
        """
        get_start_end_points()
        """
        punkt, angle = self.geo[-1].get_start_end_points(direction)
        return punkt, angle
