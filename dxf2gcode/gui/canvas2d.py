# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2011-2015
#    Christian Kohlöffel
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

"""
Special purpose canvas including all required plotting function etc.

@purpose:  Plotting all
"""

from __future__ import absolute_import
from __future__ import division

import logging

from dxf2gcode.core.point import Point
from dxf2gcode.core.shape import Shape
from dxf2gcode.core.boundingbox import BoundingBox
from dxf2gcode.core.stmove import StMove
#TODO: check if can be removed:
#from dxf2gcode.core.arcgeo import ArcGeo
from dxf2gcode.gui.wpzero import WpZero
from dxf2gcode.gui.arrow import Arrow
from dxf2gcode.gui.routetext import RouteText
from dxf2gcode.gui.canvas import CanvasBase, MyDropDownMenu

import dxf2gcode.globals.globals as g

import dxf2gcode.globals.constants as c
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsView, QRubberBand, QGraphicsScene, QGraphicsLineItem
from PyQt5.QtGui import QPainterPath, QPen, QColor, QPainterPathStroker
from PyQt5 import QtCore


logger = logging.getLogger("DxfImport.myCanvasClass")


class MyGraphicsView(CanvasBase):
    """
    This is the used Canvas to print the graphical interface of dxf2gcode.
    All GUI things should be performed in the View and plotting functions in
    the scene
    """

    def __init__(self, parent=None):
        """
        Initialisation of the View Object. This is called by the gui created
        with the QTDesigner.
        @param parent: Main is passed as a pointer for reference.
        """
        super(MyGraphicsView, self).__init__(parent)
        self.currentItem = None

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        # self.setDragMode(QGraphicsView.RubberBandDrag )
        self.setDragMode(QGraphicsView.NoDrag)

        self.parent = parent
        self.mppos = None

        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.prvRectRubberBand = QtCore.QRect()

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QtCore.QCoreApplication.translate('MyGraphicsView',
                                                           string_to_translate))

    def contextMenuEvent(self, event):
        """
        Create the contextmenu.
        @purpose: Links the new Class of ContextMenu to Graphicsview.
        """
        position = self.mapToGlobal(event.pos())
        GVPos = self.mapToScene(event.pos())
        real_pos = Point(GVPos.x(), -GVPos.y())

        menu = MyDropDownMenu(self.scene(), position, real_pos)

    def wheelEvent(self, event):
        """
        With Mouse Wheel the object is scaled
        @purpose: Scale by mouse wheel
        @param event: Event Parameters passed to function
        """
        delta = event.angleDelta().y()
        scale = (1000 + delta) / 1000.0
        self.scale(scale, scale)

    def mousePressEvent(self, event):
        """
        Right Mouse click shall have no function, Therefore pass only left
        click event
        @purpose: Change inherited mousePressEvent
        @param event: Event Parameters passed to function
        """

        if self.dragMode() == 1:
            super(MyGraphicsView, self).mousePressEvent(event)
        elif event.button() == QtCore.Qt.LeftButton:
            self.mppos = event.pos()
        else:
            pass

    def mouseReleaseEvent(self, event):
        """
        Right Mouse click shall have no function, Therefore pass only left
        click event
        @purpose: Change inherited mousePressEvent
        @param event: Event Parameters passed to function
        """
        delta = 2

        if self.dragMode() == 1:
            # if (event.key() == QtCore.Qt.Key_Shift):
            # self.setDragMode(QGraphicsView.NoDrag)
            super(MyGraphicsView, self).mouseReleaseEvent(event)

        # Selection only enabled for left Button
        elif event.button() == QtCore.Qt.LeftButton:
            self.currentItems = []
            scene = self.scene()
            if scene and not self.isMultiSelect:
                for item in scene.selectedItems():
                    item.setSelected(False, False)
            # If the mouse button is pressed without movement of rubberband
            if self.rubberBand.isHidden():
                rect = QtCore.QRect(event.pos().x()-delta,
                                    event.pos().y() - delta,
                                    2 * delta, 2*delta)
                # logger.debug(rect)

                point = self.mapToScene(event.pos())
                min_distance = float(0x7fffffff)
                for item in self.items(rect):
                    itemDistance = item.contains_point(point)
                    if itemDistance < min_distance:
                        min_distance = itemDistance
                        self.currentItems = item
                if self.currentItems:
                    if self.currentItems.isSelected():
                        self.currentItems.setSelected(False, False)
                    else:
                        self.currentItems.setSelected(True, False)
            else:
                rect = self.rubberBand.geometry()
                self.currentItems = self.items(rect)
                self.rubberBand.hide()
                # logger.debug("Rubberband Selection")

                # All items in the selection
                # self.currentItems = self.items(rect)
                # print self.currentItems
                # logger.debug(rect)

                for item in self.currentItems:
                    if item.isSelected():
                        item.setSelected(False, False)
                    else:
                        # print (item.flags())
                        item.setSelected(True, False)

        else:
            pass

        self.mppos = None
        # super(MyGraphicsView, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """
        MouseMoveEvent of the Graphiscview. May also be used for the Statusbar.
        @purpose: Get the MouseMoveEvent and use it for the Rubberband Selection
        @param event: Event Parameters passed to function
        """
        if self.mppos is not None:
            Point = event.pos() - self.mppos
            if Point.manhattanLength() > 3:
                # print 'the mouse has moved more than 3 pixels since the oldPosition'
                # print "Mouse Pointer is currently hovering at: ", event.pos()
                rect = QtCore.QRect(self.mppos, event.pos())
                '''
                The following is needed because of PyQt5 doesn't like to switch from sign
                 it will keep displaying last rectangle, i.e. you can end up will multiple rectangles
                '''
                if self.prvRectRubberBand.width() > 0 and not rect.width() > 0 or rect.width() == 0 or\
                   self.prvRectRubberBand.height() > 0 and not rect.height() > 0 or rect.height() == 0:
                    self.rubberBand.hide()
                self.rubberBand.setGeometry(rect.normalized())
                self.rubberBand.show()
                self.prvRectRubberBand = rect

        scpoint = self.mapToScene(event.pos())

        # self.setStatusTip('X: %3.1f; Y: %3.1f' % (scpoint.x(), -scpoint.y()))
        # works not as supposed to
        self.setToolTip('X: %3.1f; Y: %3.1f' %(scpoint.x(), -scpoint.y()))

        super(MyGraphicsView, self).mouseMoveEvent(event)

    def autoscale(self):
        """
        Automatically zooms to the full extend of the current GraphicsScene
        """
        scene = self.scene()
        width = scene.BB.Pe.x - scene.BB.Ps.x
        height = scene.BB.Pe.y - scene.BB.Ps.y
        scext = QtCore.QRectF(scene.BB.Ps.x, -scene.BB.Pe.y, width * 1.05, height * 1.05)
        self.fitInView(scext, QtCore.Qt.KeepAspectRatio)
        logger.debug(self.tr("Autoscaling to extend: %s") % scext)

    def setShowPathDirections(self, flag):
        """
        This function is called by the Main Window from the Menubar.
        @param flag: This flag is true if all Path Direction shall be shown
        """
        scene = self.scene()
        for shape in scene.shapes:
            shape.starrow.setallwaysshow(flag)
            shape.enarrow.setallwaysshow(flag)
            shape.stmove.setallwaysshow(flag)

            if shape.Drill:
                shape.starrow.setallwaysshow(False)
                shape.enarrow.setallwaysshow(False)

    def resetAll(self):
        """
        Deletes the existing GraphicsScene.
        """
        scene = self.scene()
        del scene

class MyGraphicsScene(QGraphicsScene):
    """
    This is the Canvas used to print the graphical interface of dxf2gcode.
    The Scene is rendered into the previously defined mygraphicsView class.
    All performed plotting functions should be defined here.
    @sideeffect: None
    """
    def __init__(self):
        QGraphicsScene.__init__(self)

        self.shapes = []
        self.wpzero = None
        self.routearrows = []
        self.routetext = []
        self.expprv = None
        self.expcol = None
        self.expnr = 0

        self.showDisabledPaths = False

        self.BB = BoundingBox()

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QtCore.QCoreApplication.translate('MyGraphicsScene',
                                                           string_to_translate))

    def plotAll(self, shapes):
        """
        Instance is called by the Main Window after the defined file is loaded.
        It generates all ploting functionality. The parameters are generally
        used to scale or offset the base geometry (by Menu in GUI).
        """
        for shape in shapes:
            self.paint_shape(shape)
            self.addItem(shape)
            self.shapes.append(shape)
        self.draw_wp_zero()
        self.update()

    def repaint_shape(self, shape):
        # setParentItem(None) might let it crash, hence we rely on the garbage collector
        shape.stmove.hide()
        shape.starrow.hide()
        shape.enarrow.hide()
        del shape.stmove
        del shape.starrow
        del shape.enarrow
        self.paint_shape(shape)
        if not shape.isSelected():
            shape.stmove.hide()
            shape.starrow.hide()
            shape.enarrow.hide()

    def paint_shape(self, shape):
        """
        Create all plotting related parts of one shape.
        @param shape: The shape to be plotted.
        """
        start, start_ang = shape.get_start_end_points(True, True)
        shape.path = QPainterPath()
        shape.path.moveTo(start.x, -start.y)
        drawHorLine = lambda caller, start, end: shape.path.lineTo(end.x, -end.y)
        drawVerLine = lambda caller, start: None  # Not used in 2D mode
        shape.make_path(drawHorLine, drawVerLine)

        self.BB = self.BB.joinBB(shape.BB)

        shape.stmove = self.createstmove(shape)
        shape.starrow = self.createstarrow(shape)
        shape.enarrow = self.createenarrow(shape)
        shape.stmove.setParentItem(shape)
        shape.starrow.setParentItem(shape)
        shape.enarrow.setParentItem(shape)

    def draw_wp_zero(self):
        """
        This function is called while the drawing of all items is done. It plots
        the WPZero to the Point x=0 and y=0. This item will be enabled or
        disabled to be shown or not.
        """
        self.wpzero = WpZero(QtCore.QPointF(0, 0))
        self.addItem(self.wpzero)

    def createstarrow(self, shape):
        """
        This function creates the Arrows at the end point of a shape when the
        shape is selected.
        @param shape: The shape for which the Arrow shall be created.
        """

        length = 20
        start, start_ang = shape.get_start_end_points_physical(True, True, PPocket=True)
        
        arrow = Arrow(startp=start,
                      length=length,
                      angle=start_ang,
                      color=QColor(50, 200, 255),
                      pencolor=QColor(50, 100, 255))
        return arrow

    def createenarrow(self, shape):
        """
        This function creates the Arrows at the end point of a shape when the
        shape is selected.
        @param shape: The shape for which the Arrow shall be created.
        """
        length = 20
        end, end_ang = shape.get_start_end_points_physical(False, True, PPocket=shape.Pocket)
            
        arrow = Arrow(startp=end,
                      length=length,
                      angle=end_ang,
                      color=QColor(0, 245, 100),
                      pencolor=QColor(0, 180, 50),
                      startarrow=False)
        return arrow

    def createstmove(self, shape):
        """
        This function creates the Additional Start and End Moves in the plot
        window when the shape is selected
        @param shape: The shape for which the Move shall be created.
        """
        stmove = StMoveGUI(shape)
        return stmove

    def delete_opt_paths(self):
        """
        This function deletes all the plotted export routes.
        """
        # removeItem might let it crash, hence we rely on the garbage collector
        while self.routearrows:
            item = self.routearrows.pop()
            item.hide()
            del item

        while self.routetext:
            item = self.routetext.pop()
            item.hide()
            del item

    def addexproutest(self):
        self.expprv = Point(g.config.vars.Plane_Coordinates['axis1_start_end'],
                            g.config.vars.Plane_Coordinates['axis2_start_end'])
        self.expcol = QtCore.Qt.darkRed

    def addexproute(self, exp_order, layer_nr):
        """
        This function initialises the Arrows of the export route order and its numbers.
        """
        for shape_nr in range(len(exp_order)):
            shape = self.shapes[exp_order[shape_nr]]
            st = self.expprv
            if shape.Pocket == True:
                start_en_points = shape.get_start_end_points(PPocket=True)
                en = start_en_points[0]
                self.expprv = start_en_points[1]

            else:
                en, self.expprv = shape.get_start_end_points_physical()
            self.routearrows.append(Arrow(startp=en,
                                          endp=st,
                                          color=self.expcol,
                                          pencolor=self.expcol))

            self.expcol = QtCore.Qt.darkGray

            self.routetext.append(RouteText(text=("%s,%s" % (layer_nr, shape_nr+1)),
                                            startp=en))
            # self.routetext[-1].ItemIgnoresTransformations

            self.addItem(self.routearrows[-1])
            self.addItem(self.routetext[-1])

    def addexprouteen(self):
        st = self.expprv
        en = Point(g.config.vars.Plane_Coordinates['axis1_start_end'],
                   g.config.vars.Plane_Coordinates['axis2_start_end'])
        self.expcol = QtCore.Qt.darkRed

        self.routearrows.append(Arrow(startp=en,
                                      endp=st,
                                      color=self.expcol,
                                      pencolor=self.expcol))

        self.addItem(self.routearrows[-1])

    def setShowDisabledPaths(self, flag):
        """
        This function is called by the Main Menu and is passed from Main to
        MyGraphicsView to the Scene. It performs the showing or hiding
        of enabled/disabled shapes.

        @param flag: This flag is true if hidden paths shall be shown
        """
        self.showDisabledPaths = flag

        for shape in self.shapes:
            if flag and shape.isDisabled():
                shape.show()
            elif not flag and shape.isDisabled():
                shape.hide()

class ShapeGUI(QGraphicsItem, Shape):
    PEN_NORMAL = QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine)
    PEN_NORMAL.setCosmetic(True)
    PEN_SELECT = QPen(QtCore.Qt.red, 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    PEN_SELECT.setCosmetic(True)
    PEN_NORMAL_DISABLED = QPen(QtCore.Qt.gray, 1, QtCore.Qt.DotLine)
    PEN_NORMAL_DISABLED.setCosmetic(True)
    PEN_SELECT_DISABLED = QPen(QtCore.Qt.blue, 1, QtCore.Qt.DashLine)
    PEN_SELECT_DISABLED.setCosmetic(True)
    PEN_BREAK = QPen(QtCore.Qt.magenta, 1, QtCore.Qt.SolidLine)
    PEN_BREAK.setCosmetic(True)
    PEN_LEFT = QPen(QtCore.Qt.darkCyan, 1, QtCore.Qt.SolidLine)
    PEN_LEFT.setCosmetic(True)
    PEN_RIGHT = QPen(QtCore.Qt.darkMagenta, 1, QtCore.Qt.SolidLine)
    PEN_RIGHT.setCosmetic(True)

    def __init__(self, nr, closed, parentEntity):
        QGraphicsItem.__init__(self)
        Shape.__init__(self, nr, closed, parentEntity)

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

        self.selectionChangedCallback = None
        self.enableDisableCallback = None

        self.starrow = None
        self.enarrow = None

    def __str__(self):
        return super(ShapeGUI, self).__str__()

    def tr(self, string_to_translate):
        return super(ShapeGUI, self).tr(string_to_translate)

    def contains_point(self, point):
        """
        Method to determine the minimal distance from the point to the shape
        @param point: a QPointF
        @return: minimal distance
        """
        min_distance = float(0x7fffffff)
        ref_point = Point(point.x(), point.y())
        t = 0.0
        while t < 1.0:
            per_point = self.path.pointAtPercent(t)
            spline_point = Point(per_point.x(), per_point.y())
            distance = ref_point.distance(spline_point)
            if distance < min_distance:
                min_distance = distance
            t += 0.01
        return min_distance

    def setSelectionChangedCallback(self, callback):
        """
        Register a callback function in order to inform parents when the selection has changed.
        Note: we can't use QT signals here because ShapeClass doesn't inherits from a QObject
        @param callback: the function to be called, with the prototype callbackFunction(shape, select)
        """
        self.selectionChangedCallback = callback

    def setEnableDisableCallback(self, callback):
        """
        Register a callback function in order to inform parents when a shape has been enabled or disabled.
        Note: we can't use QT signals here because ShapeClass doesn't inherits from a QObject
        @param callback: the function to be called, with the prototype callbackFunction(shape, enabled)
        """
        self.enableDisableCallback = callback

    def setPen(self, pen):
        """
        Method to change the Pen of the outline of the object and update the
        drawing
        """
        self.pen = pen

    def paint(self, painter, option, widget):
        """
        Method will be triggered with each paint event. Possible to give options
        @param painter: Reference to std. painter
        @param option: Possible options here
        @param widget: The widget which is painted on.
        """
        if self.isSelected() and not self.isDisabled():
            painter.setPen(ShapeGUI.PEN_SELECT)
        elif not self.isDisabled():
            if self.parentLayer.isBreakLayer():
                painter.setPen(ShapeGUI.PEN_BREAK)
            elif self.cut_cor == 41:
                painter.setPen(ShapeGUI.PEN_LEFT)
            elif self.cut_cor == 42:
                painter.setPen(ShapeGUI.PEN_RIGHT)
            else:
                painter.setPen(ShapeGUI.PEN_NORMAL)
        elif self.isSelected():
            painter.setPen(ShapeGUI.PEN_SELECT_DISABLED)
        else:
            painter.setPen(ShapeGUI.PEN_NORMAL_DISABLED)

        painter.drawPath(self.path)

    def boundingRect(self):
        """
        Required method for painting. Inherited by Painterpath
        @return: Gives the Bounding Box
        """
        return self.path.boundingRect()

    def shape(self):
        """
        Reimplemented function to select outline only.
        @return: Returns the Outline only
        """
        painterStrock = QPainterPathStroker()
        painterStrock.setCurveThreshold(0.01)
        painterStrock.setWidth(0)

        stroke = painterStrock.createStroke(self.path)
        return stroke

    def setSelected(self, flag=True, blockSignals=True):
        """
        Override inherited function to turn off selection of Arrows.
        @param flag: The flag to enable or disable Selection
        """


        if Shape.isDrill(self):
            self.starrow.setSelected(False)
            self.enarrow.setSelected(False)
        else:
            self.starrow.setSelected(flag)
            self.enarrow.setSelected(flag)

        self.stmove.setSelected(flag)

        QGraphicsItem.setSelected(self, flag)
        Shape.setSelected(self, flag)

        if self.selectionChangedCallback and not blockSignals:
            self.selectionChangedCallback(self, flag)

    def setDisable(self, flag=False, blockSignals=True):
        """
        New implemented function which is in parallel to show and hide.
        @param flag: The flag to enable or disable Selection
        """
        # QGraphicsItem.setDisable(self, flag)
        Shape.setDisable(self, flag)
        scene = self.scene()

        if scene is not None:
            if not scene.showDisabledPaths and flag:
                self.hide()
                self.starrow.setSelected(False)
                self.enarrow.setSelected(False)
                self.stmove.setSelected(False)
            else:
                self.show()

        if self.enableDisableCallback and not blockSignals:
            self.enableDisableCallback(self, not flag)


class StMoveGUI(QGraphicsLineItem, StMove):

    def __init__(self, shape):
        QGraphicsLineItem.__init__(self)
        StMove.__init__(self, shape)

        self.allwaysshow = False
        self.path = QPainterPath()

        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        self.pen = QPen(QColor(50, 100, 255), 1, QtCore.Qt.SolidLine,
                        QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.pen.setCosmetic(True)
        self.make_papath()

    def contains_point(self, point):
        """
        StMove cannot be selected. Return maximal distance
        """
        return float(0x7fffffff)

    def make_papath(self):
        """
        To be called if a Shape shall be printed to the canvas
        @param canvas: The canvas to be printed in
        @param pospro: The color of the shape
        """
        self.path = QPainterPath()
        if len(self.geos):
            start = self.geos.abs_el(0).get_start_end_points(True)
            self.path.moveTo(start.x, -start.y)
        drawHorLine = lambda caller, start, end: self.path.lineTo(end.x, -end.y)
        drawVerLine = lambda caller, start: None  # Not used in 2D mode
        self.make_path(drawHorLine, drawVerLine)

    def setSelected(self, flag=True):
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
        If the directions shall be allwaysshown the parameter will be set and
        all paths will be shown.
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
        Method will be triggered with each paint event. Possible to give options
        @param painter: Reference to std. painter
        @param option: Possible options here
        @param widget: The widget which is painted on.
        """
        painter.setPen(self.pen)
        painter.drawPath(self.path)

    def boundingRect(self):
        """
        Required method for painting. Inherited by Painterpath
        @return: Gives the Bounding Box
        """
        return self.path.boundingRect()
