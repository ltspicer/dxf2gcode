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

from math import sin, cos, acos, pi
import logging

from dxf2gcode.core.point import Point

import dxf2gcode.globals.constants as c
from PyQt5.QtWidgets import QGraphicsLineItem, QGraphicsItem
from PyQt5.QtGui import QPen, QPolygonF
from PyQt5 import QtCore


logger = logging.getLogger("Gui.Arrow")


class Arrow(QGraphicsLineItem):
    def __init__(self, startp=Point(), endp=None,
                 length=60.0, angle=50.0,
                 color=QtCore.Qt.red, pencolor=QtCore.Qt.green,
                 startarrow=True):
        """
        Initialisation of the class.
        """
        self.sc = None
        super(Arrow, self).__init__()

        self.startp = QtCore.QPointF(startp.x, -startp.y)
        self.endp = endp

        self.length = length
        self.angle = angle
        self.startarrow = startarrow
        self.allwaysshow = False

        self.arrowHead = QPolygonF()
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.myColor = color
        self.pen = QPen(pencolor, 1, QtCore.Qt.SolidLine)
        self.pen.setCosmetic(True)
        self.arrowSize = 8.0

    def contains_point(self, point):
        """
        Arrows cannot be selected. Return maximal distance
        """
        return float(0x7fffffff)

    def setSelected(self, flag=True, blockSignals=True):
        """
        Override inherited function to turn off selection of Arrows.
        @param flag: The flag to enable or disable Selection
        """
        if self.allwaysshow:
            pass
        elif flag is True:
            self.show()
        else:
            self.hide()

    def setallwaysshow(self, flag=False):
        """
        If the directions shall be allwaysshown the parameter
        will be set and  all paths will be shown.
        @param flag: The flag to enable or disable Selection
        """
        self.allwaysshow = flag
        if flag is True:
            self.show()
        elif flag is True and self.isSelected():
            self.show()
        else:
            self.hide()

    def paint(self, painter, option, widget=None):
        """
        Method for painting the arrow.
        """

        demat = painter.deviceTransform()
        self.sc = demat.m11()

        if self.endp is None:
            dx = cos(self.angle) * self.length / self.sc
            dy = sin(self.angle) * self.length / self.sc

            endp = QtCore.QPointF(self.startp.x() - dx, self.startp.y() + dy)
        else:
            endp = QtCore.QPointF(self.endp.x, -self.endp.y)

        arrowSize = self.arrowSize / self.sc

        painter.setPen(self.pen)
        painter.setBrush(self.myColor)

        self.setLine(QtCore.QLineF(endp, self.startp))
        line = self.line()

        if line.length() != 0:
            angle = acos(line.dx() / line.length())

            if line.dy() >= 0:
                angle = (pi * 2.0) - angle

            if self.startarrow:
                arrowP1 = line.p2() - QtCore.QPointF(sin(angle + pi / 3.0) * arrowSize,
                                                     cos(angle + pi / 3.0) * arrowSize)
                arrowP2 = line.p2() - QtCore.QPointF(sin(angle + pi - pi / 3.0) * arrowSize,
                                                     cos(angle + pi - pi / 3.0) * arrowSize)
                self.arrowHead.clear()
                for Point in [line.p2(), arrowP1, arrowP2]:
                    self.arrowHead.append(Point)

            else:
                arrowP1 = line.p1() + QtCore.QPointF(sin(angle + pi / 3.0) * arrowSize,
                                                     cos(angle + pi / 3.0) * arrowSize)
                arrowP2 = line.p1() + QtCore.QPointF(sin(angle + pi - pi / 3.0) * arrowSize,
                                                     cos(angle + pi - pi / 3.0) * arrowSize)
                self.arrowHead.clear()
                for Point in [line.p1(), arrowP1, arrowP2]:
                    self.arrowHead.append(Point)

            painter.drawLine(line)
            painter.drawPolygon(self.arrowHead)

    def boundingRect(self):
        """
        Override inherited function to enlarge selection of Arrow to include all
        @param flag: The flag to enable or disable Selection
        """
        if not self.sc:  # since this function is called before paint; and scale is unknown
            return QtCore.QRectF(self.startp.x(), self.startp.y(), 1e-9, 1e-9)

        arrowSize = self.arrowSize / self.sc
        extra = arrowSize  # self.pen.width() +

        if self.endp is None:
            dx = cos(self.angle) * self.length / self.sc
            dy = sin(self.angle) * self.length / self.sc

            endp = QtCore.QPointF(self.startp.x() - dx, self.startp.y() + dy)
        else:
            endp = QtCore.QPointF(self.endp.x, -self.endp.y)

        brect = QtCore.QRectF(self.startp,
                              QtCore.QSizeF(endp.x()-self.startp.x(),
                                            endp.y()-self.startp.y())).normalized().adjusted(-extra, -extra, extra, extra)
        return brect
