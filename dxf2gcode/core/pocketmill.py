# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2008-2015
#    Christian Kohlöffel
#    Vinzenz Schulz
#    Jean-Paul Schouwstra
#   
#   Copyright (C) 2019-2020 
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

from __future__ import absolute_import
from __future__ import division

from math import sin, cos, pi, sqrt, ceil
from copy import deepcopy

import dxf2gcode.globals.globals as g

from dxf2gcode.core.linegeo import LineGeo
from dxf2gcode.core.arcgeo import ArcGeo
from dxf2gcode.core.point import Point
from dxf2gcode.core.intersect import Intersect
from dxf2gcode.core.shape import Geos
from dxf2gcode.core.shape import Shape
from dxf2gcode.core.shapeoffset import *
from dxf2gcode.core.pocketmove import PocketMove

import logging
logger = logging.getLogger('core.pocketmill')

import time

class InterPoint(object):
    def __init__(self, x=0, y=0, i=0, mill = False):
        self.x = x
        self.y = y
        self.i = i
        self.mill = mill
        self.p = Point(x, y)
        
    def __str__ (self):
        return 'X ->%6.3f  Y ->%6.3f (%s) is %s' % (self.x, self.y, self.i, self.mill)
    
    def setMill(self, mill=False):
        self.mill = mill
        ### end of not-inside
        
class BBArray(object):
    def __init__(self, bbStartPoint, bbEndPoint, diff):
        #This class creates array filled with points (self.create())
        # they will be used to decide where to mill lines
        self.array = []
        self.any = False
        
        #Start point - top, right
        
        if bbStartPoint.x > bbEndPoint.x:
            self.xStart = bbEndPoint.x
            self.xEnd   = bbStartPoint.x
        else: 
            self.xStart = bbStartPoint.x
            self.xEnd   = bbEndPoint.x

        if bbStartPoint.y > bbEndPoint.y:
            self.yStart = bbStartPoint.y
            self.yEnd   = bbEndPoint.y
        else: 
            self.yStart = bbEndPoint.y
            self.yEnd   = bbStartPoint.y
            
        #TODO: calculate diff size based on BBArray height 
        #TODO:  and minimal maximum diff (like on circle milling)
        self.diff = diff
        self.overUpRight = Point(self.xStart + 1, self.xStart + 1)
        self.overDownLeft = Point(self.xEnd - 1, self.xEnd - 1)
        self.overDistance = self.overUpRight.distance(self.overDownLeft)
        
        self.divY = 1
        self.divX = 4
            
    def create(self):
        #Fills array with InterPoints
        arrayIndex = 0 
        yi = self.yStart - self.diff / self.divY
            
        while yi > self.yEnd:
            xi = self.xStart + self.diff/self.divX
            while xi < self.xEnd:
                self.append(InterPoint(xi, yi, arrayIndex, True))
                xi += self.diff/self.divX
                arrayIndex += 1
            yi -= self.diff / self.divY
            
    def checkIfAny(self):
        #Checks if any of points is set to be milled
        any = False
        
        for point in self.array:
            if point.mill == True:
                any = True
                break

        return any
        
    def append(self, newPoint):
        #Adds point to array
        self.array.append(newPoint)
    
    def print(self):
        #This will stop work if array will be not in order
        #This function tries to dump to stdout whole array
        # in somehow readable way.
        yi = self.array[0].y
        print("%8.2f" % (yi) , end = "\t")
        
        for BBPoint in self.array:
                
            if BBPoint.y != yi:
                yi = BBPoint.y 
                print()
                print("%8.2f" % (yi) , end = "\t")
                
            if BBPoint.mill:
                print('T', end = ' ')
            else:
                print(' ', end = ' ')
                    
        print()
        
    def removeLine(self, line):
        #Sets points in array to mill=False
        # if they lay on line
        if line.Ps.x > line.Pe.x:
            line = LineGeo(line.Pe, line.Ps)
        
        for BBPoint in self.array:
            if BBPoint.y == line.Ps.y and line.Pe.x >= BBPoint.x and BBPoint.x >= line.Ps.x:
                BBPoint.setMill(False)
                
    def findHorizontalWithPoint(self, point):
        #Search array to find maximum lenght line that contains given point
        #values outside the box
        closestFalseLeft = self.xStart - 1
        closestFalseRight = self.xEnd + 1
        
        closestTrueLeft = point.x
        closestTrueRight = point.x
        
        #go left and right and find closest Falses
        for aPoint in self.array:
            if aPoint.mill == False and aPoint.y == point.y:
                if aPoint.x < point.x and closestFalseLeft < aPoint.x:
                    closestFalseLeft = aPoint.x
                    
                if aPoint.x > point.x and closestFalseRight > aPoint.x:
                    closestFalseRight = aPoint.x
        
        #print("False x'ses: %s and %s" % (closestFalseLeft, closestFalseRight))
        
        #now find closest True's to those points
        for aPoint in self.array:
            if aPoint.mill == True and aPoint.y == point.y:
                #looking for most-left (smallest x) True
                #before (bigger than) closestFalseLeft
                #smaller than point
                if aPoint.x < point.x and aPoint.x > closestFalseLeft and aPoint.x < closestTrueLeft:
                    closestTrueLeft = aPoint.x
                    
                if aPoint.x > point.x and aPoint.x < closestFalseRight and aPoint.x > closestTrueRight:
                    closestTrueRight = aPoint.x
        
        if point.distance(Point(closestTrueLeft, point.y)) < point.distance(Point(closestTrueRight, point.y)):
            return LineGeo(Point(closestTrueLeft, point.y), Point(closestTrueRight, point.y))
        else:
            return LineGeo(Point(closestTrueRight, point.y), Point(closestTrueLeft, point.y))
    
    def findNextLine(self, line, preferTop):
        #Tries to find line over or under given line to be milled.
        # It prefers top or bottom, and returns new preferences ;)
        # It returns preferTop = True if it finds Bottom.
        bottomY = self.yEnd - 1
        topY    = self.yStart + 1
        currentY = line.Ps.y
        currentX = line.Pe.x
        
        #find closest top and bottom Y
        for BBPoint in self.array:
            #We do not check if it is set to mill, since
            # we want to eliminate lines that are too far
            #if BBPoint.y == currentY and BBPoint.mill == True:
            #    topY = currentY
            #    bottomY = currentY
            #    break
            if topY > BBPoint.y and currentY < BBPoint.y:
                topY = BBPoint.y
            if bottomY < BBPoint.y and currentY > BBPoint.y:
                bottomY = BBPoint.y
                
        print("topY: %s, bottomY: %s." % (topY, bottomY))
        
        if line.Ps.x < line.Pe.x:
            xRangeStart = line.Ps.x
            xRangeEnd   = line.Pe.x
        else:
            xRangeStart = line.Pe.x
            xRangeEnd   = line.Ps.x
        
        xListTop = []
        xListBottom = []
        
        #create two lists of X'es in "good" range
        for BBPoint in self.array:
            if BBPoint.mill == True and xRangeStart <= BBPoint.x <= xRangeEnd:
                if BBPoint.y == topY:
                    xListTop.append(BBPoint.x)
                elif BBPoint.y == bottomY:
                    xListBottom.append(BBPoint.x)
                            
        if (preferTop == True or len(xListBottom) == 0) and len(xListTop) > 0:
            if abs(currentX - min(xListTop)) > abs(currentX - max(xListTop)):
                #return Line(Point(max(xListTop), topY), Point(min(xListTop), topY))
                return self.findHorizontalWithPoint(Point(max(xListTop), topY)), False
            else:
                return self.findHorizontalWithPoint(Point(min(xListTop), topY)), False
        elif (preferTop == False or len(xListTop) == 0) and len(xListBottom) > 0:
            if abs(currentX - min(xListBottom)) > abs(currentX - max(xListBottom)):
                return self.findHorizontalWithPoint(Point(max(xListBottom), bottomY)), True
            else:
                return self.findHorizontalWithPoint(Point(min(xListBottom), bottomY)), True
        else:
            print("preferTop is %s, bottom len: %s, top len: %s." % (preferTop, len(xListBottom), len(xListTop)))
            return None, preferTop
                
        
    def findClosestEnd(self, point):
        #Looks for most-bottom and most-top y's.
        # For those two looks for most-lefts and most-rights.
        # Then checks which one is closest, so milling will start 
        # from closest most-far line and most-close point.
        bottomY    = self.yStart + 1
        topY = self.yEnd - 1
        
        for BBPoint in self.array:
            if BBPoint.mill == True:
                if BBPoint.y > topY:
                    topY = BBPoint.y
                if BBPoint.y < bottomY:
                    bottomY = BBPoint.y
        
        topLeftX     = self.xEnd - 1 
        topRightX    = self.xStart + 1
        bottomLeftX  = self.xEnd - 1
        bottomRightX = self.xStart + 1
        
        for BBPoint in self.array:
            if BBPoint.mill == True:
                if BBPoint.y == topY:
                    if BBPoint.x < topLeftX:
                        topLeftX = BBPoint.x
                    if BBPoint.x > topRightX:
                        topRightX = BBPoint.x
                if BBPoint.y == bottomY:
                    if BBPoint.x < bottomLeftX:
                        bottomLeftX = BBPoint.x
                    if BBPoint.x > bottomRightX:
                        bottomRightX = BBPoint.x
                        
        points = [
            Point(topLeftX, topY),
            Point(topRightX, topY),
            Point(bottomLeftX, bottomY),
            Point(bottomRightX, bottomY)]
        
        distance = self.overDistance
        closestPoint = None
        
        for p in points:
            #print("Extreme: %s." % (p))
            if point.distance(p) < distance:
                distance = point.distance(p)
                closestPoint = p
                
        return closestPoint        
    
class PocketMill(object):
    def __init__(self, stmove=None):
        #It gets stmove object and do whole magic with it:
        # creates paths for pocket milling
        self.stmove = stmove
        
        # Get tool radius based on tool diameter.
        self.tool_rad = self.stmove.shape.parentLayer.getToolRadius()
        
        self.bbarray = 0
        
        self.arrayYStart = 0
        self.arrayYEnd = 0
        self.arrayXStart = 0
        self.arrayXEnd = 0
        
        self.diff = 0
        
        self.dist = 0
        
        self.inters = []
                
    def removeNearShape(self):
        #Looks for points in array that are too close to shape
        # to be milled.
        for BBPoint in self.bbarray.array:
            #check only points that are meant to be milled
            if BBPoint.mill == True:
                #check if this point is not too close to any geo in shape
                for geo in self.stmove.shape.geos.abs_iter():
                    if isinstance(geo, LineGeo):
                        if geo.distance_l_p(BBPoint.p) < self.dist:
                            BBPoint.setMill(False)
                            break
                    elif isinstance(geo, ArcGeo):
                        if geo.distance_a_p(BBPoint.p) < self.dist:
                            BBPoint.setMill(False)
                            break
    def movePoint(self, point):
        #Moves point by particular value (addX and Y are
        # calculated before creating "point")
        #in fact point is an array [point, addX, addY]
        return [Point(point[0].x + point[1], point[0].y + point[2]), point[1], point[2]]
                        
    def removeOutOfShape(self):
        #Check all points in array if they are inside (self.inters) or
        # outside shape. If they are outside, it sets them 
        # to mill= False
        for BBPoint in self.bbarray.array:
            count = 0
            
            if BBPoint.mill == True:
                for pinter in self.inters:
                    if pinter.y == BBPoint.y and pinter.x > BBPoint.x:
                        count += 1
            
            if count%2 == 0:
                BBPoint.setMill(False)
            
    def createInterList(self):
        yi = self.bbarray.yStart - self.diff/self.bbarray.divY
        #this while loop will prepare points that crosses the shape.
        # it will be used later to check if point lays inside shape.
        # imagine horizontal line from particular point up to the end
        # of BBox containing shape. if the line crosses shape even times
        # we are outside the shape.
        
        while yi > self.bbarray.yEnd:
            for interGeo in self.stmove.shape.geos.abs_iter():
                if isinstance(interGeo, LineGeo):   
                    if interGeo.Ps.x == interGeo.Pe.x:
                        #this is vertical line
                        #check if obvius intersection lays on finite line
                        if yi > min(interGeo.Ps.y, interGeo.Pe.y) and yi < max(interGeo.Ps.y, interGeo.Pe.y):
                            self.inters.append(Point(interGeo.Pe.x, yi))
                        continue
                    
                    #calculate line coords
                    lineA = (interGeo.Ps.y - interGeo.Pe.y)/(interGeo.Ps.x - interGeo.Pe.x)
                    lineB = interGeo.Ps.y - lineA * interGeo.Ps.x
                    
                    if lineA == 0:
                        #TODO: check if shape like this:
                        #  \____
                        #       \
                        # won't cause problem...
                        #
                        #print("Horizontal!")
                        continue
                    
                    #TODO: joints will propably cause problems
                    
                    interX = (yi - lineB)/lineA
                    
                    #check if intersection does belong to line
                    if interX < min(interGeo.Ps.x, interGeo.Pe.x) or interX > max(interGeo.Ps.x, interGeo.Pe.x):
                        continue 
                    
                    self.inters.append(Point(interX, yi))
                    
                elif isinstance(interGeo, ArcGeo):
                    #based on intersect.py:line_arc_intersect
                    baX = self.bbarray.xEnd - self.bbarray.xStart
                    baY = 0
                    caX = interGeo.O.x - self.bbarray.xStart
                    caY = interGeo.O.y - yi

                    a = baX * baX + baY * baY
                    bBy2 = baX * caX + baY * caY
                    c = caX * caX + caY * caY - interGeo.r * interGeo.r

                    if a == 0:
                        continue

                    pBy2 = bBy2 / a
                    q = c / a

                    disc = pBy2 * pBy2 - q
                    if disc > 0:
                        tmpSqrt = sqrt(disc)
                        abScalingFactor1 = -pBy2 + tmpSqrt
                        abScalingFactor2 = -pBy2 - tmpSqrt

                        p1 = Point(self.bbarray.xStart - baX * abScalingFactor1,
                                yi - baY * abScalingFactor1)
                        p2 = Point(self.bbarray.xStart - baX * abScalingFactor2,
                                yi - baY * abScalingFactor2)
                        
                        linex = sorted([self.bbarray.xStart, self.bbarray.xEnd])
                        liney = sorted([yi, yi])
                        
                        ang = interGeo.dif_ang(interGeo.Ps, p1, interGeo.ext)
                        
                        if interGeo.ext > 0:
                            arcOut = interGeo.ext + 1e-8 >= ang >= -1e-8
                        else:
                            arcOut = interGeo.ext - 1e-8 <= ang <= 1e-8
                        
                        if  linex[0] - 1e-8 <= p1.x and p1.x <= linex[1] + 1e-8 and liney[0] - 1e-8 <= p1.y and p1.y <= liney[1] + 1e-8 and arcOut:
                                #print("Good point! %s" % (p1))
                                self.inters.append(p1)
                                
                        ang = interGeo.dif_ang(interGeo.Ps, p2, interGeo.ext)
                        
                        if interGeo.ext > 0:
                            arcOut = interGeo.ext + 1e-8 >= ang >= -1e-8
                        else:
                            arcOut = interGeo.ext - 1e-8 <= ang <= 1e-8
                        
                        if  linex[0] - 1e-8 <= p2.x <= linex[1] + 1e-8 and liney[0] - 1e-8 <= p2.y <= liney[1] + 1e-8 and arcOut:
                                #print("Good point! %s" % (p2))
                                self.inters.append(p2)
                                
            yi -= self.diff/self.bbarray.divY
            #print("End of finding intersections")
        
    def createLines(self):
        #This function will decide what kind of shape do we deal with
        # then creates milling lines and move paths.
        circle = 0
        horizontalRectangle = 0
        
        geosNum = len(self.stmove.shape.geos)
        print("Number of geos: %s" % (geosNum))
        
        cutComp = self.stmove.shape.cut_cor
            
        if cutComp == 40: #no compensation
            realStart = self.stmove.shape.geos[0].Ps
        else:
            realStart = self.stmove.geos[-1].Pe
        
        #set the proper direction for the tool path
        if self.stmove.shape.cw ==True:
            direction = -1;
        else:
            direction = 1;
        
        if geosNum == 2:
            if self.stmove.shape.geos[0].r == self.stmove.shape.geos[1].r and self.stmove.shape.geos[0].Ps == self.stmove.shape.geos[1].Pe and self.stmove.shape.geos[0].Pe == self.stmove.shape.geos[1].Ps:
                    circle = 1
                    
        if geosNum == 4:
            hLines = 0
            vLines = 0
            linesNum = 0
            
            for gLine in self.stmove.shape.geos:
                if isinstance(gLine, LineGeo) and gLine.Ps.x == gLine.Pe.x:
                    vLines += 1
                if isinstance(gLine, LineGeo) and gLine.Ps.y == gLine.Pe.y:
                    hLines += 1
                    
            if hLines == 2 and vLines == 2:
                horizontalRectangle = 1
                
        currentPoint = self.stmove.start
            
        if False:
            print("beans shape")
            #TODO: beans shape:  (____)
        elif False:
            #TODO: "Only lines and <180 angle.
            print("Only lines and <180 angle.")
        elif circle == 1:
            stepOverlay = 0.9
            
            #this is radius of whole shape
            if cutComp == 40: #no compensation
                millRad = self.stmove.shape.geos[0].r - self.tool_rad
            elif cutComp == 41: #outside
                millRad = self.stmove.shape.geos[0].r
            elif cutComp == 42: #comp inside
                millRad = self.stmove.shape.geos[0].r - 2 * self.tool_rad
            
            rotNum = (millRad - 2 * self.tool_rad * stepOverlay)/(self.tool_rad * (1 + stepOverlay))
            rotNum = ceil(rotNum)
                        
            stepOverlay = (millRad - rotNum * self.tool_rad)/(self.tool_rad * 2 * rotNum)
            currentRad = millRad - self.tool_rad * stepOverlay
            
            circleOff = self.tool_rad * (1 + stepOverlay)
            
            centerPoint = self.stmove.shape.geos[0].O
            print("Shape radius: %s, circle rotNum: %s, stepOverlay: %s." % (self.stmove.shape.geos[0].r, rotNum + 1, stepOverlay))
            
            currentPoint = realStart
            rLimit = self.tool_rad * (1 - stepOverlay)
            
            while currentRad > rLimit:
                
                print("CurrentRad: %s, limit %s." % (currentRad, rLimit))
                
                goToPoint = Point(centerPoint.x + currentRad, centerPoint.y)
                
                if centerPoint.y == currentPoint.y and centerPoint.x < currentPoint.x:
                    self.stmove.append(LineGeo(currentPoint, goToPoint))
                else:
                    self.stmove.append(PocketMove(currentPoint, goToPoint))
                    
                currentPoint = goToPoint
                
                self.stmove.append(ArcGeo(Ps = currentPoint, Pe = currentPoint, O = centerPoint, r = currentRad, direction = direction))
                
                currentRad -= circleOff
                
            self.stmove.append(PocketMove(currentPoint, realStart))
                        
        elif horizontalRectangle == 1:
            #rad varsus rad*2^(1/2) is 0,707106781
            stepOverlay = 0.7
            #hRectangleOff = 0.7 * self.tool_rad
            startTop = 0
            startLeft = 0
            
            #calculate center point
            xes = []
            yes = []
            
            for geo in self.stmove.shape.geos:
                xes.append(geo.Ps.x)
                yes.append(geo.Ps.y)
                
            centerPoint = Point(sum(xes)/4, sum(yes)/4)
            
            if realStart.x < centerPoint.x and realStart.y < centerPoint.y:
                #start is left-bottom corner
                print("start is left-bottom corner")
                startTop = 0
                startLeft = 1
                
            elif realStart.x > centerPoint.x and realStart.y < centerPoint.y:
                print("start is right-bottom corner")
                startTop = 0
                startLeft = 0
                
            elif realStart.x < centerPoint.x and realStart.y > centerPoint.y:
                print("start is left-top corner")
                startTop = 1
                startLeft = 1
                
            elif realStart.x > centerPoint.x and realStart.y > centerPoint.y:
                print("start is right-top corner")
                startTop = 1
                startLeft = 0
            
            #distance between center and farrest mill line
            xOff = abs(centerPoint.x - self.stmove.shape.geos[0].Ps.x)
            yOff = abs(centerPoint.y - self.stmove.shape.geos[0].Ps.y)
            
            if self.stmove.shape.cut_cor == 41:
                xOff += self.tool_rad
                yOff += self.tool_rad
            elif self.stmove.shape.cut_cor == 42:
                xOff -= self.tool_rad
                yOff -= self.tool_rad
            
            #Off = 2*stepOverlay*self.tool_rad + n*(1+stepOverlay)*self.tool_rad + tool_rad
            # n*(1+stepOverlay)*self.tool_rad = Off - 2*stepOverlay*self.tool_rad - tool_rad
            # n = (Off - 2*stepOverlay*self.tool_rad - tool_rad)/((1+stepOverlay)*self.tool_rad)
            numRotX = (xOff - 2*stepOverlay*self.tool_rad - self.tool_rad)/(self.tool_rad * (1 + stepOverlay))
            numRotY = (yOff - 2*stepOverlay*self.tool_rad - self.tool_rad)/(self.tool_rad * (1 + stepOverlay))
            
            numRot = ceil(min(numRotX, numRotY))
            
            #Off = 2*stepOverlay*self.tool_rad + n*(1+stepOverlay)*self.tool_rad + tool_rad
            # Off - tool_rad - n*self.tool_rad = 2*stepOverlay*self.tool_rad + n*stepOverlay*self.tool_rad
            # (Off - tool_rad - n*self.tool_rad)/(2*self.tool_rad + n*self.tool_rad) = stepOverlay
            stepOverlayX = (xOff - numRot * self.tool_rad - self.tool_rad)/((numRot + 2) * self.tool_rad)
            stepOverlayY = (yOff - numRot * self.tool_rad - self.tool_rad)/((numRot + 2) * self.tool_rad)
            
            if stepOverlayX > stepOverlay:
                stepOverlayX = stepOverlay
                
            if stepOverlayY > stepOverlay:
                stepOverlayY = stepOverlay
            
            print("Number of rotations: %s." % (numRot))
            
            #check first point and where it is
            # and build array of points calculated
            # from self.tool_rad and first point
            # for CW and CCW
            pointLeftBottom = Point(centerPoint.x - xOff + self.tool_rad * (1 + stepOverlayX),
                                centerPoint.y - yOff + self.tool_rad * (1 + stepOverlayY))
            
            pointLeftTop = Point(centerPoint.x - xOff + self.tool_rad * (1 + stepOverlayX),
                                centerPoint.y + yOff - self.tool_rad * (1 + stepOverlayY))
            
            pointRightTop = Point(centerPoint.x + xOff - self.tool_rad * (1 + stepOverlayX),
                                centerPoint.y + yOff - self.tool_rad * (1 + stepOverlayY))
            
            pointRightBottom = Point(centerPoint.x + xOff - self.tool_rad * (1 + stepOverlayX),
                                centerPoint.y - yOff + self.tool_rad * (1 + stepOverlayY))
            
            #also calculade addX and addY values, so next time 
            # corner-point will be in right place.
            stepX = (1 + stepOverlayX) * self.tool_rad
            stepY = (1 + stepOverlayY) * self.tool_rad 
            
            if startLeft == 1 and startTop == 0:
                pointList = [
                    [pointLeftBottom, Point(stepX, 0)],
                    [pointLeftTop, Point(stepX, -stepY)],
                    [pointRightTop, Point(-stepX, -stepY)],
                    [pointRightBottom, Point(-stepX, stepY)]
                    ]
                addAfter = Point(0, stepY)
                
            elif startLeft == 0 and startTop == 0:
                pointList = [
                    [pointRightBottom, Point(0, stepY)],
                    [pointLeftBottom, Point(stepX, stepY)],
                    [pointLeftTop, Point(stepX, -stepY)],
                    [pointRightTop, Point(-stepX, -stepY)]
                    ]
                addAfter = Point(-stepX, 0)
                
            elif startLeft == 1 and startTop == 1:
                pointList = [
                    [pointLeftTop, Point(0, -stepY)],
                    [pointRightTop, Point(-stepX, -stepY)],
                    [pointRightBottom, Point(-stepX, stepY)],
                    [pointLeftBottom, Point(stepX, stepY)]
                    ]
                addAfter = Point(stepX, 0)
                
            elif startLeft == 0 and startTop == 1:
                pointList = [
                    [pointRightTop, Point(-stepX, 0)],
                    [pointRightBottom, Point(-stepX, stepY)],
                    [pointLeftBottom, Point(stepX, stepY)],
                    [pointLeftTop, Point(stepX, -stepY)]
                    ]
                addAfter = Point(0, -stepY)
                
            #CW => -1, CCW => 1
            if direction == 1:
                #if CCW, change list direction
                tmp = pointList[1]
                pointList[1] = pointList[3]
                pointList[3] = tmp
                #correct addAfter
                tmp1 = pointList[0][1]
                pointList[0][1] = addAfter
                addAfter = tmp1
                
            #TODO: convert it to move based on horizontal and vertical lines only
            #TODO:  or check if it is needed.
            self.stmove.append(LineGeo(realStart, pointList[0][0]))
            
            i = 0
            
            #go throught all points until center
            while numRot >= i:
                print("Rot: %s/%s." % (i, numRot))
                self.stmove.append(LineGeo(pointList[0][0], pointList[1][0]))
                pointList[0][0] += pointList[0][1]
                self.stmove.append(LineGeo(pointList[1][0], pointList[2][0]))
                pointList[1][0] += pointList[1][1]
                self.stmove.append(LineGeo(pointList[2][0], pointList[3][0]))
                pointList[2][0] += pointList[2][1]
                self.stmove.append(LineGeo(pointList[3][0], pointList[0][0]))
                pointList[3][0] += pointList[3][1]
                
                currentPoint = pointList[0][0]
                i += 1
                pointList[0][0] += addAfter
                
            #go back to start point
            self.stmove.append(PocketMove(currentPoint, realStart))
            
            #done!
            
        else:
            #this is universal way to make pocket-milling
            # it (after making contour) will do zig-zag
            # inside shape. It is not extremely optimised
            # but should work for every kind of shape.
            
            #rad varsus rad*2^(1/2) is 0,707106781
            self.diff = self.tool_rad*2 * 0.7
            
            compType = self.stmove.shape.cut_cor
            
            #Compensation:
            # 42 - inside
            # 41 - outside
            # 40 - no compensation
            print("Compensations type: %s." % (compType))
            
            #print('BB: ' + self.stmove.shape.BB)
            print("self.stmove.BB: %s" % self.stmove.shape.BB)
            
            self.bbarray = BBArray(self.stmove.shape.BB.Ps, self.stmove.shape.BB.Pe, self.diff)
            
            print("BBBounds: X%s to X%s, Y%s to Y%s" % (self.bbarray.xStart, self.bbarray.xEnd, self.bbarray.yStart, self.bbarray.yEnd))
            
            #how close can be point to shape
            #TODO: tweak?
            self.dist = self.tool_rad/0.7
            
            ### fill array with TRUEs
            self.bbarray.create()
            ### end of filling array with TRUEs
            
            print("Empty array: ")
            self.bbarray.print()
            print("End of empty array.")
            
            ### check if point is not to close to shape
            #TODO: compensation type 41
            if compType == 42:
                self.removeNearShape()
            
            print("Array without Shape: ")
            self.bbarray.print()
            print("Array without Shape END.")
         
            #imagine parallel, horizontal lines (distance of self.diff)
            # this function will find all intersections of those lines
            # with shape.
            self.createInterList()
            
            self.removeOutOfShape()
            
            print("Final array:")
            self.bbarray.print()
            print("End of final array.")
                                
            ### ### ###
            ### Cool! We have now complete array of points to mill
            ### but we need to convert it into LINES now...
                    
            print("Tool rad is %s." % (self.tool_rad))
            
            currentPoint = realStart
                                    
            while self.bbarray.checkIfAny():
                #Find start for new zig-zag and go there.
                closestPoint = self.bbarray.findClosestEnd(currentPoint)
                closestLine = self.bbarray.findHorizontalWithPoint(closestPoint)
                print("Closest end line to start is %s." % (closestLine))
                print("Closest point to start is %s." % (closestPoint))
                goToPoint = closestLine.Ps
                
                #line = LineGeo(currentPoint, goToPoint)
                
                #self.stmove.append(line)
                self.stmove.append(PocketMove(currentPoint, goToPoint))
                currentPoint = goToPoint
                
                preferTop = True
                                                
                while True:
                    #currentPoint should be one of bbarray.mill = true now
                    # so we are between Ps and Pe of next line at Y height
                    #Do first line from starting point 
                    line = self.bbarray.findHorizontalWithPoint(currentPoint)    #dir
                    
                    #print("Line at Y%8.2f: from X%8.2f to X%8.2f." % (line.Ps.y, line.Ps.x, line.Pe.x))
                    
                    #If we are not at start point, go there
                    if currentPoint.x != line.Ps.x:
                        self.stmove.append(LineGeo(currentPoint, line.Ps))                        
                    
                    self.stmove.append(line)
                    self.bbarray.removeLine(line)
                    currentPoint = line.Pe
                    
                    #Now we need to check if there is any near line we can go
                    line, preferTop = self.bbarray.findNextLine(line, preferTop)
                    
                    if line == None:
                        print("Done.")
                        break
                    else:
                        print("Closest line is %s x %s => %s x %s." % (line.Ps.x, line.Ps.y, line.Pe.x, line.Pe.y))
                    
                    #check if we can go straight up, or we need to do some stuff...
                    if not (line.Ps.x <= currentPoint.x <= line.Pe.x or line.Ps.x >= currentPoint.x >= line.Pe.x):
                        #we need to do some stuff: go back under next line
                        goToPoint = Point(line.Ps.x, currentPoint.y)
                        self.stmove.append(LineGeo(currentPoint, goToPoint))
                        currentPoint = goToPoint
                        
                    #Ok, go straight up, and end on nextLine (somewhere 
                    # between or on start/end point
                    goToPoint = Point(currentPoint.x, line.Ps.y)
                    self.stmove.append(LineGeo(currentPoint, goToPoint))
                    currentPoint = goToPoint
                            
                print("Removed lines.")
                self.bbarray.print()

                #self.stmove.append(LineGeo(currentPoint, self.stmove.end))
            self.stmove.append(PocketMove(currentPoint, realStart))
