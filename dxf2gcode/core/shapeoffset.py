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

from math import pi, sqrt, sin, cos
from copy import deepcopy
import logging

from dxf2gcode.core.linegeo import LineGeo
from dxf2gcode.core.arcgeo import ArcGeo
from dxf2gcode.core.point import Point
from dxf2gcode.core.shape import Geos
from dxf2gcode.core.shape import Shape

logger = logging.getLogger('core.shapeoffset')

eps = 1e-6
min_length=0.01



class offShapeClass(Shape):

    """
    This Class is used to generate The fofset aof a shape according to:
    "A pair-wise offset Algorithm for 2D point sequence curve"
    http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.101.8855
    """

    def __init__(self, parent=None, offset=1, offtype='in'):
        """
        Standard method to initialize the class
        @param closed: Gives information about the shape, when it is closed
        this value becomes 1. Closed means it is a Polygon, otherwise it is a
        Polyline
        @param length: The total length of the shape including all geometries
        @param geos: The list with all geometries included in the shape. May
        also contain arcs. These will be reflected by multiple lines in order
        to easy calclations.
        """

        super(offShapeClass, self).__init__(nr=parent.nr,
                                            closed=parent.closed,
                                            geos=[])

        #logger.debug("The shape is: %s" % (self.closed))

        self.offset = offset
        self.offtype = offtype
        self.segments = Geos()
        self.rawoff = []

        self.geos_preprocessing(parent)

        self.make_segment_types()

        nextConvexPoint = [
            e for e in self.segments if isinstance(e, ConvexPoint)]
        # logger.debug(nextConvexPoint)
        # nextConvexPoint=[nextConvexPoint[31]]
        self.counter = 0

        while len(nextConvexPoint):  # [self.convex_vertex[-1]]:
            convex_vertex_nr = self.segments.index(nextConvexPoint[0])

            try:
                forward, backward = self.PairWiseInterferenceDetection(
                    convex_vertex_nr + 1, convex_vertex_nr - 1)
            except:
                logger.warning("Not able to finish cutter compensation without error - Skipping it")
                return
                break

            if forward is None:
                return
                break

            if (backward == 0 and
                    forward == (len(self.segments) - 1) and
                    self.closed):
                self.segments = Geos()
                break

            # Make Raw offset curve of forward and backward segment
            fw_rawoff_seg = self.make_rawoff_seg(self.segments[forward])
            bw_rawoff_seg = self.make_rawoff_seg(self.segments[backward])

            # Intersect the two segements
            iPoint = fw_rawoff_seg.find_inter_point(bw_rawoff_seg, typ="TIP")


            if iPoint is None:
                logger.debug("forward: %s, backward: %s, iPoint: %s" % (
                    forward, backward, iPoint))
                logger.debug("fw_rawoff_seg: %s, bw_rawoff_seg: %s" % 
                             (fw_rawoff_seg, bw_rawoff_seg))

                logger.warning("No intersection found?!")
                self.segments = Geos()
                return

            if isinstance(iPoint, list):
                logger.debug("forward: %s, backward: %s, iPoint: %s" % (
                    forward, backward, iPoint))
                logger.debug("fw_rawoff_seg: %s, bw_rawoff_seg: %s" % 
                             (fw_rawoff_seg, bw_rawoff_seg))
                logger.debug(iPoint[0])
                logger.debug(iPoint[1])
                logger.warning("Found more then one intersection points?! Using first one")
                iPoint = iPoint[0]


            # Remove the LIR from the PS Curce
            self.remove_LIR(forward, backward, iPoint)
            nextConvexPoint = [
                e for e in self.segments if isinstance(e, ConvexPoint)]
            # logger.debug(nextConvexPoint)
            # nextConvexPoint=[]
            # logger.debug(nextConvexPoint)

        for seg in self.segments:
            self.rawoff += [self.make_rawoff_seg(seg)]


        self.geos_postprocessing(eps*5)
        #SweepLine(geos=self.rawoff, closed=self.closed)

        # If parent shape is ccw, switch direction
        if parent.cw != self.cw:
            self.reverse()

    def __repr__(self):
        """
        Standard method to print the object
        @return: A string
        """

        return "\nnr:          %i" % self.nr + \
               "\nclosed:      %s" % self.closed + \
               "\ngeos:        %s" % self.geos + \
               "\nofftype:     %s" % self.offtype + \
               "\noffset:      %s" % self.offset + \
               "\nsegments:    %s" % self.segments + \
               "\nrawoff       %s" % self.rawoff

    def reverse(self, geos=None):
        super().reverse(geos)
        # If working with own geometry, toggle rawoff direction too
        if not geos:
            self.rawoff.reverse()
            for geo in self.rawoff:
                geo.reverse()

    def geos_preprocessing(self, parent):
        """
        Do all the preprocessing required in order to have working offset
         algorithm.
        @param parent: The parent shape including the geometries to
        be offsetted.
        """
        
        logging.debug("Doing Preprocessing")

        self.geos = Geos([])
        if self.closed:
            last_Pe = parent.geos[-1].Pe.rot_sca_abs(parent=parent.parentEntity)
        else:
            last_Pe = None

        for geo in parent.geos:
            if isinstance(geo, LineGeo):
                new_geo = OffLineGeo(geo=geo, parent=parent.parentEntity)
            elif isinstance(geo, ArcGeo):
                new_geo = OffArcGeo(geo=geo, parent=parent.parentEntity)
            else:
                logger.error("Should not be here")

            if last_Pe is not None:
                #                 logger.debug("Current distance: %s" %
                #                              new_geo.Ps.distance(last_Pe))
                if new_geo.Ps.distance(last_Pe) > 0.0:
                    new_geo.match_Ps_to_Pe(last_Pe)

#                     logger.debug("New distance: %s" %
#                                  new_geo.Ps.distance(last_Pe))

            last_Pe = new_geo.Pe

            self.geos.append(new_geo)

        self.make_shape_ccw()
        self.join_colinear_lines()

    def geos_postprocessing(self, min_length):
        """
        Do all the postprocessing required in order to have working sweepline
         algorithm.
        @param min_length: The min_length must be bigger ghen eps, otherwise 
        potential errors may occure.
        """
        #FIXME
        pass
        
        

    def make_segment_types(self):
        """
        This function is called in order to generate the segements according
        to Definiton 2.
        An edge (line) is a linear segment and a reflex vertex is is reflex
        segment. Colinear lines are assumed to be removed prior to the segment
        type definition.
        """
        # Do only if more then 2 geometies
#         if len(self.geos) < 2:
#             return

        # Start with first Vertex if the line is closed
        if self.closed:
            start = 0
        else:
            start = 1
            geo1 = self.geos[0]
            if isinstance(geo1, LineGeo):
                geo1.start_normal = geo1.Ps.get_normal_vector(geo1.Pe)
                geo1.end_normal = geo1.Ps.get_normal_vector(geo1.Pe)
            else:
                geo1.start_normal = geo1.O.unit_vector(geo1.Ps, r=1)
                geo1.end_normal = geo1.O.unit_vector(geo1.Pe, r=1)
                if geo1.ext < 0:
                    geo1.start_normal = geo1.start_normal * -1
                    geo1.end_normal = geo1.end_normal * -1
            self.segments += [geo1]

        for i in range(start, len(self.geos)):
            geo1 = self.geos[i - 1]
            geo2 = self.geos[i]

            if i == start:
                if isinstance(geo1, LineGeo):
                    geo1.start_normal = geo1.Ps.get_normal_vector(geo1.Pe)
                    geo1.end_normal = geo1.Ps.get_normal_vector(geo1.Pe)
                else:
                    geo1.start_normal = geo1.O.unit_vector(geo1.Ps, r=1)
                    geo1.end_normal = geo1.O.unit_vector(geo1.Pe, r=1)
                    if geo1.ext < 0:
                        geo1.start_normal = geo1.start_normal * -1
                        geo1.end_normal = geo1.end_normal * -1

            if isinstance(geo2, LineGeo):
                geo2.start_normal = geo2.Ps.get_normal_vector(geo2.Pe)
                geo2.end_normal = geo2.Ps.get_normal_vector(geo2.Pe)
            elif isinstance(geo2, ArcGeo):
                geo2.start_normal = geo2.O.unit_vector(geo2.Ps, r=1)
                geo2.end_normal = geo2.O.unit_vector(geo2.Pe, r=1)
                if geo2.ext < 0:
                    geo2.start_normal = geo2.start_normal * -1
                    geo2.end_normal = geo2.end_normal * -1
                    
            if ((isinstance(geo2, ArcGeo)) and
                    ((self.offtype == "out" and geo2.ext > 0) or
                     (self.offtype == "in" and geo2.ext < 0)) and
                    ((geo2.r - abs(self.offset)) < -eps)):

                newgeo2 = ConvexPoint(geo2.O.x, geo2.O.y)
                newgeo2.start_normal = geo2.start_normal
                newgeo2.end_normal = geo2.end_normal
                geo2 = newgeo2

            if (((geo1.Pe.ccw(geo1.Pe + geo1.end_normal,
                              geo1.Pe + geo1.end_normal + 
                              geo2.start_normal) == 1) and
                 self.offtype == "in") or
                (geo1.Pe.ccw(geo1.Pe + geo1.end_normal,
                             geo1.Pe + geo1.end_normal + 
                             geo2.start_normal) == -1 and
                 self.offtype == "out")):

                reflexPe = OffPoint(x=geo1.Pe.x, y=geo1.Pe.y)
                reflexPe.start_normal = geo1.end_normal
                reflexPe.end_normal = geo2.start_normal
                self.segments += [reflexPe, geo2]
                
            elif (geo1.Pe.ccw(geo1.Pe + geo1.end_normal,
                              geo1.Pe + geo1.end_normal + 
                              geo2.start_normal) == 0):
                self.segments += [geo2]

            # Add the linear segment which is a line connecting 2 vertices
            else:
                self.segments += [ConvexPoint(geo1.Pe.x, geo1.Pe.y), geo2]
            
    def make_rawoff_seg(self, seg):
        """
        This function returns the rawoffset of a segement. A line for a line
        and a circle for a reflex segement.
        @param segment_nr: The nr of the segement for which the rawoffset
        segement shall be generated
        @ return: Returns the rawoffsetsegement of the  defined segment
        """

        # seg=self.segments[segment_nr]

        if self.offtype == "out":
            offset = -abs(self.offset)
        else:
            offset = abs(self.offset)

        # if segement 1 is inverted change End Point
        if isinstance(seg, OffLineGeo):
            Ps = seg.Ps + seg.start_normal * offset
            Pe = seg.Pe + seg.end_normal * offset

            return OffLineGeo(Ps, Pe)

        elif isinstance(seg, OffPoint):
            Ps = seg + seg.start_normal * offset
            Pe = seg + seg.end_normal * offset

            return OffArcGeo(Ps=Ps, Pe=Pe, O=deepcopy(seg),
                             r=self.offset, direction=offset)
        elif isinstance(seg, OffArcGeo):
            Ps = seg.Ps + seg.start_normal * offset
            Pe = seg.Pe + seg.end_normal * offset

            # logger.debug(seg.Ps)
            # logger.debug(seg.Pe)
            # logger.debug(seg.start_normal)
            # logger.debug(seg.end_normal)                         

            if seg.ext > 0:
                return OffArcGeo(Ps=Ps, Pe=Pe, O=seg.O,
                                 r=seg.r + offset, direction=seg.ext)
            else:
                return OffArcGeo(Ps=Ps, Pe=Pe, O=seg.O,
                                 r=seg.r - offset, direction=seg.ext)    

        elif isinstance(seg, ConvexPoint):
            Ps = seg + seg.start_normal * offset
            Pe = seg + seg.end_normal * offset
            return OffArcGeo(Ps=Ps, Pe=Pe, O=deepcopy(seg),
                             r=self.offset, direction=offset)
        else:
            logger.error("Unsupportet Object type: %s" % type(seg))

    def interfering_full(self, segment1, direction, segment2):
        """
        Check if the Endpoint (dependent on direction) of segment 1 is
        interfering with segment 2 Definition according to Definition 6
        @param segment 1: The first segment
        @param direction: The direction of the line 1, as given -1 reversed
        @param segment 2: The second segment to be checked
        @ return: Returns True or False
        """

#         if isinstance(segment1, ConvexPoint):
#             logger.debug("Should not be here")
#             return False
#         else:
#             offGeo = self.make_rawoff_seg(segment1)
# self.interferingshapes += [offGeo]
#
#         if isinstance(segment1, OffPoint):
#             offGeo = segment1
#         elif direction == 1:
#             offGeo = segment1.Pe
#         elif direction == -1:
#             offGeo = segment1.Ps
# #
# logger.debug(offGeo)
#         logger.debug("Full distance: %s" % segment2.distance(offGeo))
# If the distance from the Line to the Center of the Tangential Circle
# is smaller then the radius we have an intersection
#         return segment2.distance(offGeo) <= abs(self.offset) + eps

        # if segement 1 is inverted change End Point
        if isinstance(segment1, OffLineGeo) and direction == 1:
            Pe = segment1.Pe
        elif isinstance(segment1, OffLineGeo) and direction == -1:
            Pe = segment1.Ps
        elif isinstance(segment1, ConvexPoint):
            return False
        elif isinstance(segment1, OffPoint):
            Pe = segment1
        elif isinstance(segment1, OffArcGeo) and direction == 1:
            Pe = segment1.Pe
        elif isinstance(segment1, OffArcGeo) and direction == -1:
            Pe = segment1.Ps
        else:
            logger.error("Unsupportet Object type: %s" % type(segment1))

        # if we cut outside reverse the offset
        if self.offtype == "out":
            offset = -abs(self.offset)
        else:
            offset = abs(self.offset)

        if direction == 1:
            distance = segment2.distance(Pe + segment1.end_normal * offset)

        else:
            distance = segment2.distance(Pe + segment1.start_normal * offset)

        # logger.debug("Full distance: %s" % distance)

        # If the distance from the Segment to the Center of the Tangential
        # Circle is smaller then the radius we have an intersection
        return distance <= abs(offset) + eps

    def interfering_partly(self, segment1, direction, segment2):
        """
        Check if any tangential circle of segment 1 is interfering with
        segment 2. Definition according to Definition 5
        @param segment 1: The first Line
        @param direction: The direction of the segment 1, as given -1 reversed
        @param segment 2: The second line to be checked
        @ return: Returns True or False
        """
        if isinstance(segment1, ConvexPoint):
            logger.debug("Should not be here")
            logger.debug(segment1)
            return False
            # offGeo = self.make_rawoff_seg(segment1)
            
        else:
            offGeo = self.make_rawoff_seg(segment1)
#
        # logger.debug(offGeo)
        # logger.debug("Partly distance: %s" % segment2.distance(offGeo))
        
        # If the distance from the Line to the Center of the Tangential Circle
        # is smaller then the radius we have an intersection
        return segment2.distance(offGeo) <= abs(self.offset) + eps

    def Interfering_relation(self, segment1, segment2):
        """
        Check the interfering relation between two segements (segment1 and
        segment2). Definition acccording to Definition 6
        @param segment1: The first segment (forward)
        @param segment2: The second segment (backward)
        @return: Returns one of [full, partial, reverse, None] interfering
        relations for both segments
        """
        # Check if segments are equal
        if segment1 == segment2:
            return None, None

        if self.interfering_full(segment1, 1, segment2):
            L1_status = "full"
        elif self.interfering_partly(segment1, 1, segment2):
            L1_status = "partial"
        else:
            L1_status = "reverse"

        if self.interfering_full(segment2, -1, segment1):
            L2_status = "full"
        elif self.interfering_partly(segment2, -1, segment1):
            L2_status = "partial"
        else:
            L2_status = "reverse"

        # logger.debug("Start Status: L1_status: %s,L2_status: %s"
        # % (L1_status, L2_status))

        return [L1_status, L2_status]

    def PairWiseInterferenceDetection(self, forward, backward,):
        """
        Returns the first forward and backward segment nr. for which both
        interfering conditions are partly.
        @param foward: The nr of the first forward segment
        @param backward: the nr. of the first backward segment
        @return: forward, backward
        """
        val = 2000
        logger.debug(len(self.segments))
        # self.counter = 0

        try:
            SPoint=self.segments[forward].Ps
        except:
            logger.warning("Cannot do cutter compensation, please check file / diamter of tool")
            return

        L1_status, L2_status = "full", "full"
        # Repeat until we reached the Partial-interfering-relation
        while not(L1_status == "partial" and L2_status == "partial"):
            self.interferingshapes = []
            self.counter += 1

            if forward >= len(self.segments):
                forward = 0

            segment1 = self.segments[forward]
            segment2 = self.segments[backward]
            # logger.debug("segment1: %s" % segment1)
            # logger.debug("segment2: %s" % segment2)

            if isinstance(segment1, ConvexPoint):
                forward += 1
                if forward >= len(self.segments):
                    forward = 0
                segment1 = self.segments[forward]
                # logger.debug("Forward ConvexPoint")
            if isinstance(segment2, ConvexPoint):
                backward -= 1
                segment2 = self.segments[backward]

            [L1_status, L2_status] = self.Interfering_relation(
                segment1, segment2)
            # logger.debug("Start Status: L1_status: %s,L2_status: %s"
            #             % (L1_status, L2_status))

            """
            The reverse interfering segment is replaced  by the first
            non-reverse-interfering segment along it's tracking direction
            """
            if L1_status == "reverse":
                while L1_status == "reverse":
                    self.counter += 1
                    # logger.debug(self.counter)
                    if self.counter > val:
                        break
                    if self.counter >= val:
                        self.interferingshapes = []
                    forward += 1
                    if forward >= len(self.segments):
                        forward = 0
                    segment1 = self.segments[forward]

                    if isinstance(segment1, ConvexPoint):
                        forward += 1
                        if forward >= len(self.segments):
                            forward = 0
                        segment1 = self.segments[forward]
                        # logger.debug("Forward ConvexPoint")

#                     logger.debug("Reverse Replace: forward: %s, backward: %s"
#                                  % (forward, backward))

                    [L1_status, L2_status] = self.Interfering_relation(
                        segment1, segment2)
#                     logger.debug("Checking: forward: %s, backward: %s"
#                                  %(forward, backward))
#                     logger.debug("Replace Rev.: L1_status: %s,L2_status: %s"
#                                  %(L1_status,L2_status))

            elif L2_status == "reverse":
                while L2_status == "reverse":
                    self.counter += 1
                    # logger.debug(self.counter)
                    if self.counter > val:
                        break
                    if self.counter >= val:
                        self.interferingshapes = []
                    backward -= 1
#                     logger.debug("Reverse Replace: forward: %s, backward: %s"
#                                  % (forward, backward))
                    segment2 = self.segments[backward]

                    if isinstance(segment2, ConvexPoint):
                        backward -= 1
                        segment2 = self.segments[backward]
                        # logger.debug("Backward ConvexPoint")

                    [L1_status, L2_status] = self.Interfering_relation(
                        segment1, segment2)
#                     logger.debug("Checking: forward: %s, backward: %s"
#                                  % (forward, backward))
#                     logger.debug("Replace Rev.: L1_status: %s,L2_status: %s"
#                                  % (L1_status, L2_status))

            """
            Full interfering segment is replaced by the nexst segemnt along the
            tracking direction.
            """
            if L1_status == "full" and (L2_status == "partial" or
                                        L2_status == "full"):
                forward += 1
            elif L2_status == "full" and (L1_status == "partial" or
                                          L1_status == "partial"):
                backward -= 1

            # If The begin end point is the end end point we are done.
            if L1_status is None and L2_status is None:
                logger.debug("Begin = End; Remove all; SPoint: %s", SPoint)
                return len(self.segments) - 1, 0

            # logger.debug(self.counter)
            # logger.debug("L1_status: %s,L2_status:
            # %s" %(L1_status,L2_status))
            if self.counter == val:
                self.interferingshapes = []

            if self.counter > val:  # 26:
                logger.error("No partial - partial status found")
                return None, None

        # logger.debug("Result: forward: %s, backward: %s"
        # %(forward, backward))
        return forward, backward

    def remove_LIR(self, forward, backward, iPoint):
        """
        The instance is used to remove the LIR from the PS curve.
        @param forward: The forward segment of the LIR
        @param backward: The backward segement of the LIR
        @param iPoint: The Intersection point of the LIR
        """
        if backward > forward:
            pop_range = self.segments[backward + 1:len(self.segments)]
            pop_range += self.segments[0:forward]
        elif backward < 0:
            pop_range = self.segments[
                len(self.segments) + backward + 1:len(self.segments)]
            pop_range += self.segments[0:forward]
        else:
            pop_range = self.segments[backward + 1:forward]

        if self.offtype == "out":
            rev = True
        else:
            rev = False
        # Modify the first segment and the last segment of the LIR
        self.segments[forward] = self.segments[
            forward].trim(Point=iPoint, dir=1, rev_norm=rev)
        self.segments[backward] = self.segments[
            backward].trim(Point=iPoint, dir=-1, rev_norm=rev)

        # Remove the segments which are inbetween the LIR
        self.segments = Geos([x for x in self.segments if x not in pop_range])


class SweepLine:

    def __init__(self, geos=[], closed=True):
        """
        The init function of the SweepLine Class. It is calling a sweep line
        algorithm in order to find all intersection of the given geometries
        @param geos: A list with geometries in their ordered structure.
        @param closed: If the geometries are closed (Polyline or Polygon)
        """

        self.geos = []
        self.found =[]
        self.closed = closed

        self.sweep_array = []
        self.intersections = []

        self.add_to_sweep_array(geos, self.closed)
        #logger.debug("Sweep Array created")
        self.search_intersections()
        
        logger.debug(self.found)
        for ele in self.found:
            logger.debug(ele)

    def __repr__(self):
        """
        Standard method to print the object
        @return: A string
        """
        sweep_array_order = []
        for element in self.sweep_array:
            add_array = []
            rem_array = []
            swoop_array = []

            for add_ele in element.add:
                add_array.append(add_ele.nr)
            for rem_ele in element.remove:
                rem_array.append(rem_ele.nr)
            for swoop_ele in element.swoop:
                swoop_array.append(swoop_ele)

            sweep_array_order += [[element.Point.x,
                                   element.Point.y],
                                  add_array,
                                  rem_array,
                                  swoop_array]

        return ('\nlen(geos):   %i' % len(self.geos)) + \
               ('\nclosed:      %i' % self.closed) + \
               ('\ngeos:        %s' % self.geos) + \
               ('\nsweep_array_order:  %s' % sweep_array_order)

    def add_to_sweep_array(self, geos=[], closed=True):
        """
        This instance adds the given geometries to the sweep array.
        If there are already some defined it will just continue to
        add them. This may be used to get the intersection of two shapes
        @param: the geometries to be added
        @param: if these geometries are closed shape or not
        """
        from functools import cmp_to_key

        sweep_array = []
        self.geos += geos

        for geo_nr in range(len(geos)):
            geo = geos[geo_nr]
            geo.iPoints = []
            y_val = (geo.BB.Ps.y + geo.BB.Pe.y) / 2

            geo.neighbors = []
            geo.nr = geo_nr
            geo.Point = Point(x=geo.BB.Ps.x, y=y_val)

            # Add the neighbors before the geometrie
            if geo_nr == 0 and closed:
                geo.neighbors.append(geos[geo_nr - 1])
            else:
                geo.neighbors.append(geos[geo_nr - 1])

            # Add the neighbors after the geometrie
            if geo_nr == len(geos) - 1 and closed:
                geo.neighbors.append(geos[0])
            else:
                geo.neighbors.append(geos[geo_nr + 1])

            y_val = (geo.BB.Ps.y + geo.BB.Pe.y) / 2
            sweep_array.append(
                SweepElement(Point=geo.Point, add=[geo], remove=[]))
            sweep_array.append(
                SweepElement(Point=Point(x=geo.BB.Pe.x, y=y_val),
                             add=[],
                             remove=[geo]))

        sweep_array.sort(key=cmp_to_key(self.cmp_SweepElement))

        # Remove all Points which are there twice
        self.sweep_array = [sweep_array[0]]
        for ele_nr in range(1, len(sweep_array)):
            if abs(self.sweep_array[-1].Point.x - 
                   sweep_array[ele_nr].Point.x) < eps:
                self.sweep_array[-1].add += sweep_array[ele_nr].add
                self.sweep_array[-1].remove += sweep_array[ele_nr].remove
            else:
                self.sweep_array.append(sweep_array[ele_nr])

    def cmp_asscending_arc(self, P1, P2):
        """
        Compare Function for the sorting of Intersection Points on
        one common ARC
        @param P1: The first Point to be compared
        @param P2: The secon Point to be compared
        @return: 1 if the distance to the start point of P1 is bigger
        """

        # The angle between startpoint and where the intersection occures
        d_ang1 = (self.O.norm_angle(P1) - self.s_ang) % (2 * pi)
        d_ang2 = (self.O.norm_angle(P2) - self.s_ang) % (2 * pi)

        # Correct by 2*pi if the direction is wrong
        if self.ext < 0.0:
            d_ang1 -= 2 * pi
            d_ang2 -= 2 * pi

        if d_ang1 > d_ang2:
            return 1
        elif d_ang1 == d_ang2:
            return 0
        else:
            return -1

    def cmp_asscending_line(self, P1, P2):
        """
        Compare Function for the sorting of Intersection points on
        one common LINE
        @param P1: The first Point to be compared
        @param P2: The secon Point to be compared
        @return: 1 if the distance to the start point of P1 is bigger
        """
        d1 = P1.distance(self.Ps)
        d2 = P2.distance(self.Ps)

        if d1 > d2:
            return 1
        elif d1 == d2:
            return 0
        else:
            return -1

    def cmp_SweepElement(self, ele1, ele2):
        """
        Compare Function for the sorting of the sweep array.
        @param Point1: First SweepElement point for compare
        @param Point2: The second SweepElement point for the compare
        @return: True or false whichever is bigger.
        """
        if ele1.Point.x < ele2.Point.x:
            return -1
        elif ele1.Point.x > ele2.Point.x:
            return 1
        else:
            return 0

    def cmp_SweepElementy(self, ele1, ele2):
        """
        Compare Function for the sorting of the sweep array
        just in y direction.
        @param ele1: First SweepElement point for compare
        @param ele2: The second SweepElement point for the compare
        @return: True or false whichever is bigger.
        """
        # logger.debug(ele1)
        # logger.debug(ele2)

        if ele1.Point.y < ele2.Point.y:
            return -1
        elif ele1.Point.y > ele2.Point.y:
            return 1
        else:
            return 0

    def search_intersections(self):
        """
        This instance is called to search all intersection
        points between the Elements defined in geos
        """
        from functools import cmp_to_key
        
        search_array = []
        self.found = []
        ele_nr = 0

        while ele_nr < len(self.sweep_array):
            ele = self.sweep_array[ele_nr]
            ele_nr += 1
            #logger.debug(ele.add)

            for geo in ele.add:
                search_array.append(geo)
                search_array.sort(key=cmp_to_key(self.cmp_SweepElementy))
                index = search_array.index(geo)

                if len(search_array) >= 2:
                    if index > 0:
                        self.search_geo_intersection(
                            geo, search_array[index - 1])

                    if index < (len(search_array) - 1):
                        self.search_geo_intersection(
                            geo, search_array[index + 1])

            #logger.debug(ele.swoop)
#             for geo in ele.swoop:
#                 # The y values of the elements are exchanged and the upper and
#                 # lower neighbors are checked for intersections
#                 
#                 logger.debug(geo)
#                 #logger.debug(geo[0])
#                 #logger.debug(geo[1])
# 
#                 y0 = geo[0].Point.y
#                 y1 = geo[1].Point.y
#                 
#                 logger.debug("geht1")
# 
#                 geo[1].Point.y = y0
#                 geo[0].Point.y = y1
#                 
#                 logger.debug("geht2")
# 
# 
#                 logger.debug(search_array)
#                 logger.debug(geo[0])
#                 index0 = search_array.index(geo[0])
#                 index1 = search_array.index(geo[1])
#                 logger.debug("Pre sort index: %s, %s" %(index0,index1))
# 
#                 search_array.sort(key=cmp_to_key(self.cmp_SweepElementy))
# 
#                 index0 = search_array.index(geo[0])
#                 index1 = search_array.index(geo[1])
#                 logger.debug("Post sort index: %s, %s" %(index0,index1))
# 
#                 min_ind = min(index0, index1)
#                 max_ind = max(index0, index1)
#                 if min_ind > 0:
#                     self.search_geo_intersection(
#                         search_array[min_ind], search_array[min_ind - 1])
#                     
# 
#                 if max_ind < (len(search_array) - 1):
#                     self.search_geo_intersection(
#                         search_array[max_ind], search_array[max_ind + 1])

            for geo in ele.remove:
                index = search_array.index(geo)
                #logger.debug("remove_index: %s" %index)

                search_array.pop(index)
                if len(search_array) >= 2:
                    if index > 0 and index <= (len(search_array) - 1):
                        self.search_geo_intersection(
                            search_array[index - 1], search_array[index])

    def search_geo_intersection(self, geo1, geo2):
        """
        This function is called so search the intersections and to add
        the intersection point to the sweep array. This is called during
        each search
        """
        from functools import cmp_to_key
        #logger.debug("geo1: %s\ngeo2: %s" %(geo1,geo2))
        #logger.debug(geo1.neighbors)
        iPoint = (geo1.find_inter_point(geo2))

        if (not(iPoint is None) and
                not(geo2 in geo1.neighbors)):
            
            if isinstance(iPoint,list):
                #FIXME
                logger.error("More the none iPoint")
            else:
                iPoint = IntPoint(Point=iPoint, geo1=geo1, geo2=geo2)
                
#             logger.debug(iPoint)
#             logger.debug([geo2])
#             logger.debug(geo1.neighbors[0])
#             logger.debug(geo1.neighbors[1])
#             logger.debug(geo2)


            # if there is only one instersection
            if isinstance(iPoint, IntPoint):
                self.found.append(iPoint)
                geo1.iPoints += [iPoint]
                geo2.iPoints += [iPoint]

                self.sweep_array.append(
                    SweepElement(Point=iPoint,
                                 add=[],
                                 remove=[],
                                 swoop=[[geo1, geo2]]))

            else:
                self.found += iPoint
                geo1.iPoints += iPoint
                geo2.iPoints += iPoint
                self.sweep_array.append(
                    SweepElement(Point=iPoint[0],
                                 add=[],
                                 remove=[],
                                 swoop=[[geo1, geo2]]))
                self.sweep_array.append(
                    SweepElement(Point=iPoint[1],
                                 add=[],
                                 remove=[],
                                 swoop=[[geo1, geo2]]))

            self.sweep_array.sort(key=cmp_to_key(self.cmp_SweepElement))

class SweepElement:

    def __init__(self, Point=Point(0, 0), add=[], remove=[], swoop=[]):
        """
        This is the class for each SweepElement given in the sweep_array
        @param Point: the Point of the SweepElement (e.g. 2 Points per LineGeo)
        @param add: The geometrie to be added
        @param remove: The geometrie to be removed

        """
        self.Point = Point
        self.add = add
        self.remove = remove
        self.swoop = swoop

    def __repr__(self):
        """
        Standard method to print the object
        @return: A string
        """
        return ('\nPoint:     %s ' % (self.Point)) + \
               ('\nadd:       %s ' % self.add) + \
               ('\nremove:    %s ' % self.remove)


class OffArcGeo(ArcGeo):

    """
    Inherited Class for Shapeoffset only. All related offset functions
    are concentrated here in orde to keep base classes as clean as possible.
    """

    def __init__(self, Ps=None, Pe=None, O=None, r=1,
                 s_ang=None, e_ang=None, direction=1, drag=False, **kwargs):
        """
        Standard Method to initialize the ArcGeo. Not all of the parameters are
        required to fully define a arc. eg. Ps and Pe may be given or s_ang and
        e_ang
        @param Ps: The Start Point of the arc
        @param Pe: the End Point of the arc
        @param O: The center of the arc
        @param r: The radius of the arc
        @param s_ang: The Start Angle of the arc
        @param e_ang: the End Angle of the arc
        @param direction: The arc direction where 1 is in positive direction
        """

        if ("geo" in kwargs) and ("parent" in kwargs):
            geo = kwargs["geo"]
            parent = kwargs["parent"]

            Ps = geo.Ps.rot_sca_abs(parent=parent)
            Pe = geo.Pe.rot_sca_abs(parent=parent)
            O = geo.O.rot_sca_abs(parent=parent)
            r = geo.scaled_r(geo.r, parent)

            direction = 1 if geo.ext > 0.0 else -1

            if parent is not None and parent.sca[0] * parent.sca[1] < 0.0:
                direction *= -1

        ArcGeo.__init__(self, Ps=Ps, Pe=Pe, O=O, r=r,
                        s_ang=s_ang, e_ang=e_ang,
                        direction=direction, drag=drag)

    def distance(self, other):
        """
        Find the distance between 2 geometry elements. Possible is LineGeo
        and ArcGeo
        @param other: the instance of the 2nd geometry element.
        @return: The distance between the two geometries
        """
        """
        Find the distance between 2 geometry elements. Possible is Point,
        LineGeo and ArcGeo
        @param other: the instance of the 2nd geometry element.
        @return: The distance between the two geometries
        """

        if isinstance(other, LineGeo):
            return other.distance_l_a(self)
        elif isinstance(other, Point):
            return self.distance_a_p(other)
        elif isinstance(other, ArcGeo):
            return self.distance_a_a(other)
        else:
            logger.error(
                self.tr("Unsupported geometry type: %s" % type(other)))

    def distance_a_a(self, other):
        """
        Find the distance between two arcs
        @param other: the instance of the 2nd geometry element.
        @return: The distance between the two geometries
        """
        # logger.error('Unsupported function')
        Pself = self.get_nearest_point(other)
        Pother = other.get_nearest_point(self)
        return Pself.distance(Pother)

    def find_inter_point(self, other=[], typ='TIP'):
        """
        Find the intersection between 2 geometry elements.
        Possible is CCLineGeo and ArcGeo
        @param other: the instance of the 2nd geometry element.
        @param typ: Can be "TIP" for True Intersection Point or "Ray" for
        Intersection which is in Ray (of Line)
        @return: a list of intersection points.
        """
        if isinstance(other, LineGeo):
            IPoints = other.find_inter_point_l_a(self, typ)
            return IPoints
        elif isinstance(other, ArcGeo):
            return self.find_inter_point_a_a(other, typ)
        else:
            logger.error("Unsupported Instance: %s" % other.type)

    def find_inter_point_a_a(self, other, typ='TIP'):
        """
        Find the intersection between 2 ArcGeo elements. There can be only one
        intersection between 2 lines.
        @param other: the instance of the 2nd geometry element.
        @param typ: Can be "TIP" for True Intersection Point or "Ray" for
        Intersection which is in Ray (of Line)
        @return: a list of intersection points.
        """

        if typ == "TIP" and self.Ps.distance(other.Pe) < eps * 5:
            return other.Pe
        elif typ == "TIP" and self.Pe.distance(other.Ps) < eps * 5:
            return other.Ps


        O_dis = self.O.distance(other.O)


        # logger.debug(self.Ps.distance(other.Pe))
        # logger.debug(self.Pe.distance(other.Ps))
        # logger.debug(O_dis)

        # If self circle is surrounded by the other no intersection
        if(O_dis < abs(self.r - other.r)):
            return None

        # If other circle is surrounded by the self no intersection
        if(O_dis < abs(other.r - self.r)):
            return None

        # If The circles are to far away from each other no intersection
        # possible
        if (O_dis > abs(other.r + self.r)):
            return None

        # If both circles have the same center and radius
        if abs(O_dis) == 0.0 and abs(self.r - other.r) == 0.0:
            Pi1 = Point(x=self.Ps.x, y=self.Ps.y)
            Pi2 = Point(x=self.Pe.x, y=self.Pe.y)

            logger.debug("Both circels have the same center and radius")
            return [Pi1, Pi2]
        # The following algorithm was found on :
        # http://www.sonoma.edu/users/w/wilsonst/Papers/Geometry/circles/default.htm

        root = ((pow(self.r + other.r, 2) - pow(O_dis, 2)) * 
                (pow(O_dis, 2) - pow(other.r - self.r, 2)))

        # If the Line is a tangent the root is 0.0.
        if root <= 0.0:
            root = 0.0
        else:
            root = sqrt(root)

        xbase = (other.O.x + self.O.x) / 2 + \
            (other.O.x - self.O.x) * \
            (pow(self.r, 2) - pow(other.r, 2)) / (2 * pow(O_dis, 2))

        ybase = (other.O.y + self.O.y) / 2 + \
            (other.O.y - self.O.y) * \
            (pow(self.r, 2) - pow(other.r, 2)) / (2 * pow(O_dis, 2))

        Pi1 = Point(x=xbase + (other.O.y - self.O.y) / 
                    (2 * pow(O_dis, 2)) * root,
                    y=ybase - (other.O.x - self.O.x) / 
                    (2 * pow(O_dis, 2)) * root)

        Pi1_v1 = self.dif_ang(self.Ps, Pi1, self.ext) / self.ext
        Pi1_v2 = other.dif_ang(other.Ps, Pi1, other.ext) / other.ext

        Pi2 = Point(x=xbase - (other.O.y - self.O.y) / 
                    (2 * pow(O_dis, 2)) * root,
                    y=ybase + (other.O.x - self.O.x) / 
                    (2 * pow(O_dis, 2)) * root)

        Pi2_v1 = self.dif_ang(self.Ps, Pi2, self.ext) / self.ext
        Pi2_v2 = other.dif_ang(other.Ps, Pi2, other.ext) / other.ext

        if typ == 'TIP':
            if ((Pi1_v1 >= 0.0 and Pi1_v1 <= 1.0 and
                 Pi1_v2 > 0.0 and Pi1_v2 <= 1.0) and
                    (Pi2_v1 >= 0.0 and Pi2_v1 <= 1.0 and
                     Pi2_v2 > 0.0 and Pi2_v2 <= 1.0)):
                if (root == 0):
                    return Pi1
                else:
                    return [Pi1, Pi2]
                logger.debug("2 Solutions found for TIP")
            elif (Pi1_v1 >= 0.0 and Pi1_v1 <= 1.0 and
                  Pi1_v2 > 0.0 and Pi1_v2 <= 1.0):
                return Pi1
            elif (Pi2_v1 >= 0.0 and Pi2_v1 <= 1.0 and
                  Pi2_v2 > 0.0 and Pi2_v2 <= 1.0):
                return Pi2
            else:
                return None
        elif typ == "Ray":
            # If the root is zero only one solution and the line is a tangent.
            if root == 0:
                return Pi1
            else:
                return [Pi1, Pi2]
        else:
            logger.error("We should not be here")

    def get_nearest_point(self, other):
        """
        Get the nearest point on the arc to another geometry.
        @param other: The Line to be nearest to
        @return: The point which is the nearest to other
        """
        if isinstance(other, LineGeo):
            return other.get_nearest_point_l_a(self, ret="arc")
        elif isinstance(other, ArcGeo):
            return self.get_nearest_point_a_a(other)
        elif isinstance(other, Point):
            return self.get_nearest_point_a_p(other)
        else:
            logger.error("Unsupported Instance: %s" % other.type)

    def get_nearest_point_a_p(self, other):
        """
        Get the nearest point to a point lieing on the arc
        @param other: The Point to be nearest to
        @return: The point which is the nearest to other
        """
        if self.intersect(other):
            return other

        PPoint = self.O.get_arc_point(self.O.norm_angle(other), r=self.r)
        if self.intersect(PPoint):
            return PPoint
        elif self.Ps.distance(other) < self.Pe.distance(other):
            return self.Ps
        else:
            return self.Pe

    def get_nearest_point_a_a(self, other):
        """
        Get the nearest point to a line lieing on the line
        @param other: The Point to be nearest to
        @return: The point which is the nearest to other
        """

        if self.intersect(other):
            return self.find_inter_point_a_a(other)

        # If Nearest point is on both Arc Segments.
        if (other.PointAng_withinArc(self.O) and
                self.PointAng_withinArc(other.O)):
            return self.O.get_arc_point(self.O.norm_angle(other.O),
                                        r=self.r)

        # If Nearest point is at one of the start/end points
        else:
            dismin = self.Ps.distance(other)
            retpoint = self.Ps

            newdis = self.Pe.distance(other)
            if newdis < dismin:
                dismin = newdis
                retpoint = self.Pe

            newdis = other.Ps.distance(self)
            if newdis < dismin:
                dismin = newdis
                retpoint = self.get_nearest_point_a_p(other.Ps)

            newdis = other.Pe.distance(self)
            if newdis < dismin:
                dismin = newdis
                retpoint = self.get_nearest_point_a_p(other.Pe)
            return retpoint

    def intersect(self, other):
        """
        Check if there is an intersection of two geometry elements
        @param, a second geometry which shall be checked for intersection
        @return: True if there is an intersection
        """
        # Do a raw check first with BoundingBox
        # logger.debug("self: %s, \nother: %s, \nintersect: %s"
        # %(self,other,self.BB.hasintersection(other.BB)))
        # logger.debug("self.BB: %s \nother.BB: %s")

        # We need to test Point first cause it has no BB
        if isinstance(other, Point):
            return self.intersect_a_p(other)
        elif not(self.BB.hasintersection(other.BB)):
            return False
        elif isinstance(other, LineGeo):
            return other.intersect_l_a(self)
        elif isinstance(other, ArcGeo):
            return self.intersect_a_a(other)
        else:
            logger.error("Unsupported Instance: %s" % other.type)

    def intersect_a_a(self, other):
        """
        Check if there is an intersection of two arcs
        @param, a second arc which shall be checked for intersection
        @return: True if there is an intersection
        """
        inter = self.find_inter_point_a_a(other)
        return not(inter is None)

    def intersect_a_p(self, other):
        """
        Check if there is an intersection of an point and a arc
        @param, a second arc which shall be checked for intersection
        @return: True if there is an intersection
        """
        # No intersection possible if point is not within radius
        if not(abs(self.O.distance(other) - self.r) < eps):
            return False
        elif self.PointAng_withinArc(other):
            return True
        else:
            return False

    def match_Ps_to_Pe(self, otherPe):
        """
        This functions adapts the geometry in the way so that the
        startpoint exactly matches the given point
        @param otherPe: This is the end point of the other geometry to
        match with
        """

        self.Ps = otherPe

        # Get the Circle center point with known Start and End Points
        self.O.x = self.Ps.x - self.r * cos(self.s_ang)
        self.O.y = self.Ps.y - self.r * sin(self.s_ang)

        self.length = self.r * abs(self.ext)

        self.calc_bounding_box()
        self.abs_geo = None

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

    def split_into_2geos(self, ipoint=Point()):
        """
        Splits the given geometry into 2 geometries. The
        geometry will be splitted at ipoint.
        @param ipoint: The Point where the intersection occures
        @return: A list of 2 ArcGeo's will be returned.
        """

        # Generate the 2 geometries and their bounding boxes.
        Arc1 = OffArcGeo(Ps=self.Ps, Pe=ipoint, r=self.r,
                         O=self.O, direction=self.ext)

        Arc2 = OffArcGeo(Ps=ipoint, Pe=self.Pe, r=self.r,
                         O=self.O, direction=self.ext)
        return [Arc1, Arc2]

    def trim(self, Point, dir=1, rev_norm=False):
        """
        This instance is used to trim the geometry at the given point. The
        point can be a point on the offset geometry a perpendicular point on
        line will be used for trimming.
        @param Point: The point / perpendicular point for new Geometry
        @param dir: The direction in which the geometry will be kept (1  means
        the beginn will be trimmed)
        @param rev_norm: If the direction of the point is on the reversed side.
        """

        # logger.debug("I'm getting trimmed: %s, %s, %s, %s"
        # % (self, Point, dir, rev_norm))
        newPoint = self.O.get_arc_point(self.O.norm_angle(Point), r=self.r)
        
        new_normal = self.O.unit_vector(newPoint, r=1)
        
        if self.ext < 0:
            new_normal = new_normal * -1
        
#         new_normal = newPoint.unit_vector(self.O, r=1)
#         
#         if self.ext<0:
#             new_normal = new_normal*-1

        # logger.debug(newPoint)
        [Arc1, Arc2] = self.split_into_2geos(newPoint)

        if dir == -1:
            new_arc = Arc1
            if hasattr(self, "end_normal"):
                # new_arc.end_normal = self.end_normal
                # new_arc.start_normal = new_normal

                new_arc.end_normal = new_normal
                new_arc.start_normal = self.start_normal
            # logger.debug(new_arc)
            return new_arc
        else:
            new_arc = Arc2
            if hasattr(self, "end_normal"):
                # new_arc.end_normal = new_normal
                # new_arc.start_normal = self.start_normal

                new_arc.end_normal = self.end_normal
                new_arc.start_normal = new_normal
            # logger.debug(new_arc)
            return new_arc


class OffLineGeo(LineGeo):

    """
    Inherited Class for Shapeoffset only. All related offset functions are
    concentrated here in orde to keep base classes as clean as possible.
    """

    def __init__(self, Ps=None, Pe=None, **kwargs):
        """
        Standard Method to initialize the LineGeo.
        @param Ps: The Start Point of the line
        @param Pe: the End Point of the line
        """

        if ("geo" in kwargs) and ("parent" in kwargs):
            geo = kwargs["geo"]
            parent = kwargs["parent"]

            Ps = geo.Ps.rot_sca_abs(parent=parent)
            Pe = geo.Pe.rot_sca_abs(parent=parent)

        LineGeo.__init__(self, Ps=Ps, Pe=Pe)

    def colinear(self, other):
        """
        Check if two lines with same point self.Pe==other.Ps are colinear. For
        Point it check if the point is colinear with the line self.
        @param other: the possibly colinear line
        """
        if isinstance(other, LineGeo):
            return ((self.Ps.ccw(self.Pe, other.Pe) == 0) and
                    (self.Ps.ccw(self.Pe, other.Ps) == 0))
        elif isinstance(other, Point):
            """
            Return true iff a, b, and c all lie on the same line."
            """
            return self.Ps.ccw(self.Pe, other) == 0
        else:
            logger.debug("Unsupported instance: %s" % type(other))

    def colinearoverlapping(self, other):
        """
        Check if the lines are colinear overlapping
        Ensure A<B, C<D, and A<=C (which you can do by simple swapping). Then:
        •if B<C, the segments are disjoint
        •if B=C, then the intersection is the single point B=C
        •if B>C, then the intersection is the segment [C, min(B, D)]
        @param other: The other line
        @return: True if they are overlapping
        """
        if not(self.colinear(other)):
            return False
        else:
            if self.Ps < self.Pe:
                A = self.Ps
                B = self.Pe
            else:
                A = self.Pe
                B = self.Ps
            if other.Ps < self.Pe:
                C = other.Ps
                D = other.Pe
            else:
                C = other.Pe
                D = other.Ps

            # Swap lines if required
            if not(A <= C):
                A, B, C, D = C, D, A, B

        if B < C:
            return False
        elif B == C:
            return False
        else:
            return True

    def colinearconnected(self, other):
        """
        Check if Lines are connected and colinear
        @param other: Another Line which will be checked
        """

        if not(self.colinear(other)):
            return False
        elif self.Ps == other.Ps:
            return True
        elif self.Pe == other.Ps:
            return True
        elif self.Ps == other.Pe:
            return True
        elif self.Pe == other.Pe:
            return True
        else:
            return False

    def distance(self, other=[]):
        """
        Find the distance between 2 geometry elements. Possible is CCLineGeo
        and ArcGeo
        @param other: the instance of the 2nd geometry element.
        @return: The distance between the two geometries
        """
        if isinstance(other, LineGeo):
            return self.distance_l_l(other)
        elif isinstance(other, Point):
            return self.distance_l_p(other)
        elif isinstance(other, ArcGeo):
            return self.distance_l_a(other)
        else:
            logger.error(
                self.tr("Unsupported geometry type: %s" % type(other)))

    def distance_l_l(self, other):
        """
        Find the distance between 2 ccLineGeo elements.
        @param other: the instance of the 2nd geometry element.
        @return: The distance between the two geometries
        """

        if self.intersect(other):
            return 0.0

        return min(self.distance_l_p(other.Ps),
                   self.distance_l_p(other.Pe),
                   other.distance_l_p(self.Ps),
                   other.distance_l_p(self.Pe))

    def distance_l_a(self, other):
        """
        Find the distance between 2 ccLineGeo elements.
        @param other: the instance of the 2nd geometry element.
        @return: The distance between the two geometries
        """

        if self.intersect(other):
            return 0.0

        # Get the nearest Point to the Center of the Arc
        POnearest = self.get_nearest_point_l_p(other.O)

        # The Line is outside of the Arc
        if other.O.distance(POnearest) > other.r:
            # If the Nearest Point is on Arc Segement it is the neares one.
            # logger.debug("Nearest Point is outside of arc")
            if other.PointAng_withinArc(POnearest):
                return POnearest.distance(other.O.get_arc_point(other.O.norm_angle(POnearest),
                                                                r=other.r))
            elif self.distance(other.Ps) < self.distance(other.Pe):
                return self.get_nearest_point(other.Ps).distance(other.Ps)
            else:
                return self.get_nearest_point(other.Pe).distance(other.Pe)

        # logger.debug("Nearest Point is Inside of arc")
        # logger.debug("self.distance(other.Ps): %s, self.distance(other.Pe):
        # %s" %(self.distance(other.Ps),self.distance(other.Pe)))
        # The Line may be inside of the ARc or cross it
        if self.distance(other.Ps) < self.distance(other.Pe):
            dis_min = self.distance(other.Ps)
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))
        else:
            dis_min = self.distance(other.Pe)
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))

        if ((other.PointAng_withinArc(self.Ps)) and
                abs(other.r - other.O.distance(self.Ps)) < dis_min):
            dis_min = abs(other.r - other.O.distance(self.Ps))
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))

        if ((other.PointAng_withinArc(self.Pe)) and
                abs((other.r - other.O.distance(self.Pe))) < dis_min):
            dis_min = abs(other.r - other.O.distance(self.Pe))
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))

        return dis_min

    def find_inter_point(self, other, typ='TIP'):
        """
        Find the intersection between 2 Geo elements. There can be only one
        intersection between 2 lines. Returns also FIP which lay on the ray.
        @param other: the instance of the 2nd geometry element.
        @param typ: Can be "TIP" for True Intersection Point or "Ray" for
        Intersection which is in Ray (of Line)
        @return: a list of intersection points.
        """
        if isinstance(other, LineGeo):
            inter = self.find_inter_point_l_l(other, typ)
            return inter
        elif isinstance(other, ArcGeo):
            inter = self.find_inter_point_l_a(other, typ)
            return inter
        else:
            logger.error("Unsupported Instance: %s" % other.type)

    def find_inter_point_l_l(self, other, typ="TIP"):
        """
        Find the intersection between 2 LineGeo elements. There can be only one
        intersection between 2 lines. Returns also FIP which lay on the ray.
        @param other: the instance of the 2nd geometry element.
        @param typ: Can be "TIP" for True Intersection Point or "Ray" for
        Intersection which is in Ray (of Line)
        @return: a list of intersection points.
        """

        if self.colinear(other):
            return None
        elif typ == 'TIP' and not(self.intersect(other)):
            return None
        elif typ == "TIP" and self.Ps.distance(other.Pe) < eps * 5:
            return other.Pe
        elif typ == "TIP" and self.Pe.distance(other.Ps) < eps * 5:
            return other.Ps

        dx1 = self.Pe.x - self.Ps.x
        dy1 = self.Pe.y - self.Ps.y

        dx2 = other.Pe.x - other.Ps.x
        dy2 = other.Pe.y - other.Ps.y

        dax = self.Ps.x - other.Ps.x
        day = self.Ps.y - other.Ps.y

        # Return nothing if one of the lines has zero length
        if (dx1 == 0 and dy1 == 0) or (dx2 == 0 and dy2 == 0):
            return None

        # If to avoid division by zero.
        try:
            if(abs(dx2) >= abs(dy2)):
                v1 = (day - dax * dy2 / dx2) / (dx1 * dy2 / dx2 - dy1)
                # v2 = (dax + v1 * dx1) / dx2
            else:
                v1 = (dax - day * dx2 / dy2) / (dy1 * dx2 / dy2 - dx1)
                # v2 = (day + v1 * dy1) / dy2
        except:
            return None

        return Point(x=self.Ps.x + v1 * dx1,
                     y=self.Ps.y + v1 * dy1)

    def find_inter_point_l_a(self, Arc, typ="TIP"):
        """
        Find the intersection between 2 Geo elements. The intersection between
        a Line and a Arc is checked here. This function is also used in the
        Arc Class to check Arc -> Line Intersection (the other way around)
        @param Arc: the instance of the 2nd geometry element.
        @param typ: Can be "TIP" for True Intersection Point or "Ray" for
        Intersection which is in Ray (of Line)
        @return: a list of intersection points.
        """

        if typ == "TIP":
            if self.Ps.distance(Arc.Pe) < eps * 5:
                return Arc.Pe
            elif self.Pe.distance(Arc.Ps) < eps * 5:
                return Arc.Ps

        Ldx = self.Pe.x - self.Ps.x
        Ldy = self.Pe.y - self.Ps.y

        # Mitternachtsformel zum berechnen der Nullpunkte der quadratischen
        # Gleichung
        a = pow(Ldx, 2) + pow(Ldy, 2)
        b = 2 * Ldx * (self.Ps.x - Arc.O.x) + 2 * Ldy * (self.Ps.y - Arc.O.y)
        c = pow(self.Ps.x - Arc.O.x, 2) + \
            pow(self.Ps.y - Arc.O.y, 2) - pow(Arc.r, 2)
        root = pow(b, 2) - 4 * a * c

        # If the value under the sqrt is negative there is no intersection.
        if root < 0 or a == 0.0:
            return None

        v1 = (-b + sqrt(root)) / (2 * a)
        v2 = (-b - sqrt(root)) / (2 * a)

        Pi1 = Point(x=self.Ps.x + v1 * Ldx,
                    y=self.Ps.y + v1 * Ldy)

        Pi2 = Point(x=self.Ps.x + v2 * Ldx,
                    y=self.Ps.y + v2 * Ldy)

        # dif_ang may return 2*pi which we should interpret as zero here!
        Pi1_v = self.mod_clamp (Arc.dif_ang(Arc.Ps, Pi1, Arc.ext), -2*pi, +2*pi) / Arc.ext
        Pi2_v = self.mod_clamp (Arc.dif_ang(Arc.Ps, Pi2, Arc.ext), -2*pi, +2*pi) / Arc.ext

        if typ == 'TIP':
            if ((Pi1_v >= 0.0 and Pi1_v <= 1.0 and self.intersect(Pi1)) and
                    (Pi1_v >= 0.0 and Pi2_v <= 1.0 and self.intersect(Pi2))):
                if (root == 0):
                    return Pi1
                else:
                    return [Pi1, Pi2]
            elif (Pi1_v >= 0.0 and Pi1_v <= 1.0 and self.intersect(Pi1)):
                return Pi1
            elif (Pi1_v >= 0.0 and Pi2_v <= 1.0 and self.intersect(Pi2)):
                return Pi2
            else:
                return None
        elif typ == "Ray":
            # If the root is zero only one solution and the line is a tangent.
            if(root == 0):
                return Pi1

            return [Pi1, Pi2]
        else:
            logger.error("We should not be here")

    @staticmethod
    def mod_clamp(val,min,max):
        if val <= min:
            return val % min
        elif val >= max:
            return val % max
        return val

    def get_nearest_point(self, other):
        """
        Get the nearest point on a line to another line lieing on the line
        @param other: The Line to be nearest to
        @return: The point which is the nearest to other
        """
        if isinstance(other, LineGeo):
            return self.get_nearest_point_l_l(other)
        elif isinstance(other, ArcGeo):
            return self.get_nearest_point_l_a(other)
        elif isinstance(other, Point):
            return self.get_nearest_point_l_p(other)
        else:
            logger.error("Unsupported Instance: %s" % other.type)

    def get_nearest_point_l_l(self, other):
        """
        Get the nearest point on a line to another line lieing on the line
        @param other: The Line to be nearest to
        @return: The point which is the nearest to other
        """
        # logger.debug(self.intersect(other))
        if self.intersect(other):
            return self.find_inter_point_l_l(other)
        min_dis = self.distance(other)
        if min_dis == self.distance_l_p(other.Ps):
            return self.get_nearest_point_l_p(other.Ps)
        elif min_dis == self.distance_l_p(other.Pe):
            return self.get_nearest_point_l_p(other.Pe)
        elif min_dis == other.distance_l_p(self.Ps):
            return self.Ps
        elif min_dis == other.distance_l_p(self.Pe):
            return self.Pe
        else:
            logger.warning("No solution found")

    def get_nearest_point_l_a(self, other, ret="line"):
        """
        Get the nearest point to a line lieing on the line
        @param other: The Point to be nearest to
        @return: The point which is the nearest to other
        """
        if self.intersect(other):
            return self.find_inter_point_l_a(other)

        # Get the nearest Point to the Center of the Arc
        POnearest = self.get_nearest_point_l_p(other.O)

        # The Line is outside of the Arc
        if other.O.distance(POnearest) > other.r:
            # If the Nearest Point is on Arc Segement it is the neares one.
            # logger.debug("Nearest Point is outside of arc")
            if other.PointAng_withinArc(POnearest):
                if ret == "line":
                    return POnearest
                elif ret == "arc":
                    return other.O.get_arc_point(other.O.norm_angle(POnearest),
                                                 r=other.r)
            elif self.distance(other.Ps) < self.distance(other.Pe):
                if ret == "line":
                    return self.get_nearest_point(other.Ps)
                elif ret == "arc":
                    return other.Ps
            else:
                if ret == "line":
                    return self.get_nearest_point(other.Pe)
                elif ret == "art":
                    return other.Pe

        # logger.debug("Nearest Point is Inside of arc")
        # logger.debug("self.distance(other.Ps): %s, self.distance(other.Pe):
        # %s" %(self.distance(other.Ps),self.distance(other.Pe)))
        # The Line may be inside of the ARc or cross it
        if self.distance(other.Ps) < self.distance(other.Pe):
            Pnearest = self.get_nearest_point(other.Ps)
            Pnother = other.Ps
            dis_min = self.distance(other.Ps)
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))
        else:
            Pnearest = self.get_nearest_point(other.Pe)
            Pnother = other.Pe
            dis_min = self.distance(other.Pe)
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))

        if ((other.PointAng_withinArc(self.Ps)) and
                abs(other.r - other.O.distance(self.Ps)) < dis_min):

            Pnearest = self.Ps
            Pnother = other.O.get_arc_point(
                other.O.norm_angle(Pnearest), r=other.r)
            dis_min = abs(other.r - other.O.distance(self.Ps))
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))

        if ((other.PointAng_withinArc(self.Pe)) and
                abs((other.r - other.O.distance(self.Pe))) < dis_min):
            Pnearest = self.Pe
            Pnother = other.O.get_arc_point(
                other.O.norm_angle(Pnearest), r=other.r)

            dis_min = abs(other.r - other.O.distance(self.Pe))
            # logger.debug("Pnearest: %s, distance: %s" %(Pnearest, dis_min))
        if ret == "line":
            return Pnearest
        elif ret == "arc":
            return Pnother

    def get_nearest_point_l_p(self, other):
        """
        Get the nearest point to a point lieing on the line
        @param other: The Point to be nearest to
        @return: The point which is the nearest to other
        """
        if self.intersect(other):
            return other

        PPoint = self.perpedicular_on_line(other)

        if self.intersect(PPoint):
            return PPoint

        if self.Ps.distance(other) < self.Pe.distance(other):
            return self.Ps
        else:
            return self.Pe

    def intersect(self, other):
        """
        Check if there is an intersection of two geometry elements
        @param, a second geometry which shall be checked for intersection
        @return: True if there is an intersection
        """
        # Do a raw check first with BoundingBox
        # logger.debug("self: %s, \nother: %s, \nintersect: %s"
        # %(self,other,self.BB.hasintersection(other.BB)))
        # logger.debug("self.BB: %s \nother.BB: %s")
        # logger.debug(self.BB.hasintersection(other.BB))
        # We need to test Point first cause it has no BB
        if isinstance(other, Point):
            return self.intersect_l_p(other)
        elif not(self.BB.hasintersection(other.BB)):
            return False
        elif isinstance(other, LineGeo):
            return self.intersect_l_l(other)
        elif isinstance(other, ArcGeo):
            return self.intersect_l_a(other)
        else:
            logger.error("Unsupported Instance: %s" % other.type)

    def intersect_l_a(self, other):
        """
        Check if there is an intersection of the two line
        @param, a second line which shall be checked for intersection
        @return: True if there is an intersection
        """
        inter = self.find_inter_point_l_a(other)
        return not(inter is None)

    def intersect_l_l(self, other):
        """
        Check if there is an intersection of the two line
        @param, a second line which shall be checked for intersection
        @return: True if there is an intersection
        """
        A = self.Ps
        B = self.Pe
        C = other.Ps
        D = other.Pe
        return A.ccw(C, D) != B.ccw(C, D) and A.ccw(B, C) != A.ccw(B, D)

    def intersect_l_p(self, Point):
        """
        Check if Point is colinear and within the Line
        @param Point: A Point which will be checked
        @return: True if point Point intersects the line segment from Ps to Pe.
        Refer to http://stackoverflow.com/questions/328107/
        how-can-you-determine-a-point-is-between-two-other-points-on-a-line-segment
        """
        # (or the degenerate case that all 3 points are coincident)
        # logger.debug(self.colinear(Point))
        return (self.colinear(Point)
                and (self.within(self.Ps.x, Point.x, self.Pe.x)
                     if self.Ps.x != self.Pe.x else
                     self.within(self.Ps.y, Point.y, self.Pe.y)))

    def join_colinear_line(self, other):
        """
        Check if the two lines are colinear connected or inside of each other,
        in this case these lines will be joined to one common line, otherwise
        return both lines
        @param other: a second line
        @return: Return one or two lines
        """
        if self.colinearconnected(other):
            return [OffLineGeo(self.Ps, other.Pe)]
        
            """
            FIXME: This is not working as expected, maybe change to a function going 
            for max distance between points. min max is comparing to 0?.
            """
        elif self.colinearoverlapping(other):
            if self.Ps < self.Pe:
                newPs = min(self.Ps, other.Ps, other.Pe)
                newPe = max(self.Pe, other.Ps, other.Pe)
            else:
                newPs = max(self.Ps, other.Ps, other.Pe)
                newPe = min(self.Pe, other.Ps, other.Pe)
            return [OffLineGeo(newPs, newPe)]
        else:
            return [self, other]

    def match_Ps_to_Pe(self, otherPe):
        """
        This functions adapts the geometry in the way so that the
        startpoint exactly matches the given point
        @param otherPe: This is the end point of the other geometry to
        match with
        """

        self.Ps = otherPe

        self.length = self.Ps.distance(self.Pe)
        self.calc_bounding_box()
        self.abs_geo = None

    def perpedicular_on_line(self, other):
        """
        This function calculates the perpendicular point on a line (or ray of
        line) with the shortest distance to the point given with other
        @param other: The point to be perpendicular to
        @return: A point which is on line and perpendicular to Point other
        @see: http://stackoverflow.com/questions/1811549/
        perpendicular-on-a-line-from-a-given-point
        """
        # first convert line to normalized unit vector
        unit_vector = self.Ps.unit_vector(self.Pe)

        # translate the point and get the dot product
        lam = ((unit_vector.x * (other.x - self.Ps.x))
               + (unit_vector.y * (other.y - self.Ps.y)))
        return Point(x=(unit_vector.x * lam) + self.Ps.x,
                     y=(unit_vector.y * lam) + self.Ps.y)

    def split_into_2geos(self, ipoint=Point()):
        """
        Splits the given geometry into 2 not self intersection geometries. The
        geometry will be splitted between ipoint and Pe.
        @param ipoint: The Point where the intersection occures
        @return: A list of 2 CCLineGeo's will be returned if Point is inside
        """
        # The Point where the geo shall be splitted
        if not(ipoint):
            return [self]
        elif self.intersect(ipoint):
            Li1 = OffLineGeo(Ps=self.Ps, Pe=ipoint)
            Li2 = OffLineGeo(Ps=ipoint, Pe=self.Pe)
            return [Li1, Li2]
        else:
            return [self]

    def trim(self, Point, dir=1, rev_norm=False):
        """
        This instance is used to trim the geometry at the given point. The
        point can be a point on the offset geometry a perpendicular point on
        line will be used for trimming.
        @param Point: The point / perpendicular point for new Geometry
        @param dir: The direction in which the geometry will be kept (1  means
        the being will be trimmed)
        """
        newPoint = self.perpedicular_on_line(Point)
        if dir == 1:
            new_line = OffLineGeo(newPoint, self.Pe)
            new_line.end_normal = self.end_normal
            new_line.start_normal = self.start_normal
            return new_line
        else:
            new_line = OffLineGeo(self.Ps, newPoint)
            new_line.end_normal = self.end_normal
            new_line.start_normal = self.start_normal
            return new_line

    def within(self, p, q, r):
        "Return true iff q is between p and r (inclusive)."
        return p <= q <= r or r <= q <= p


class OffPoint(Point):

    """
    Inherited Class for Shapeoffset only. All related offset functions are
    concentrated here in order to keep base classes as clean as possible.
    """

    def __init__(self, x=0, y=0, **kwargs):

        if ("geo" in kwargs) and ("parent" in kwargs):

            geo = kwargs["geo"]
            parent = kwargs["parent"]

            x = geo.rot_sca_abs(parent=parent).x
            y = geo.rot_sca_abs(parent=parent).y

        self.x = x
        self.y = y


class ConvexPoint(OffPoint):

    """
    Inherited Class of OffPoint required to identify Convex Points in the
    Offset algorithm..
    """

    def __init__(self, x=0, y=0):
        OffPoint.__init__(self, x=x, y=y)

    def __repr__(self):
        return 'ConvexPoint (X=%6.3f, Y=%6.3f)' % (self.x, self.y)


class IntPoint(Point):
    """
    Inherited Class of Point
    """
    def __init__(self, x=0, y=0, geo1=None, geo2=None, **kwargs):

        self.x = x
        self.y = y
        self.geo1 = geo1
        self.geo2 = geo2

        if ("Point" in kwargs):
            Point = kwargs["Point"]
            self.x = Point.x
            self.y = Point.y
        

        
#     def __repr__(self):
#         return 'X ->%6.3f  Y ->%6.3f \ngeo1: %s, \ngeo2:%s' % (self.x, self.y, self.geo1, self.geo2)
        # return ('CPoints.append(Point(x=%6.5f, y=%6.5f))' %(self.x,
        
