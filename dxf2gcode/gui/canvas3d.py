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

import logging
from math import cos, pi, radians, sin

from PyQt5.QtCore import QCoreApplication, QPoint, Qt
from PyQt5.QtGui import QColor

from dxf2gcode.core.layercontent import Shapes
from dxf2gcode.core.point import Point
from dxf2gcode.core.boundingbox import BoundingBox
from dxf2gcode.core.point3d import Point3D
from dxf2gcode.core.stmove import StMove
import dxf2gcode.globals.globals as g
from dxf2gcode.gui.canvas import CanvasBase, MyDropDownMenu


logger = logging.getLogger("Gui.Canvas")

try:
    from OpenGL import GL
except ImportError:
    raise Exception("For the 3d mode you need PyOpenGL.\n"
                    "Set mode3d to False in the config file, or install PyOpenGL to run it in 3d.")

class GLWidget(CanvasBase):
    CAM_LEFT_X = -0.5
    CAM_RIGHT_X = 0.5
    CAM_BOTTOM_Y = 0.5
    CAM_TOP_Y = -0.5
    CAM_NEAR_Z = -14.0
    CAM_FAR_Z = 14.0

    COLOR_BACKGROUND = QColor.fromHsl(160, 0, 255, 255)
    COLOR_NORMAL = QColor.fromCmykF(1.0, 0.5, 0.0, 0.0, 1.0)
    COLOR_SELECT = QColor.fromCmykF(0.0, 1.0, 0.9, 0.0, 1.0)
    COLOR_NORMAL_DISABLED = QColor.fromCmykF(1.0, 0.5, 0.0, 0.0, 0.25)
    COLOR_SELECT_DISABLED = QColor.fromCmykF(0.0, 1.0, 0.9, 0.0, 0.25)
    COLOR_ENTRY_ARROW = QColor.fromRgbF(0.0, 0.0, 1.0, 1.0)
    COLOR_EXIT_ARROW = QColor.fromRgbF(0.0, 1.0, 0.0, 1.0)
    COLOR_ROUTE = QColor.fromRgbF(0.5, 0.0, 0.0, 1.0)
    COLOR_STMOVE = QColor.fromRgbF(0.5, 0.0, 0.25, 1.0)
    COLOR_BREAK = QColor.fromRgbF(1.0, 0.0, 1.0, 0.7)
    COLOR_LEFT = QColor.fromHsl(134, 240, 130, 255)
    COLOR_RIGHT = QColor.fromHsl(186, 240, 130, 255)

    def __init__(self, parent=None):
        super(GLWidget, self).__init__(parent)

        self.shapes = Shapes([])
        self.orientation = 0
        self.wpZero = 0
        self.routearrows = []
        self.expprv = None

        self._lastPos = QPoint()

        self.posX = 0.0
        self.posY = 0.0
        self.posZ = 0.0
        self.rotX = 0.0
        self.rotY = 0.0
        self.rotZ = 0.0
        self.scale = 1.0
        self.scaleCorr = 1.0

        # total (squared) distance traveled by mouse while LMB was down
        self.clickTravelSq = 0

        self.showPathDirections = False
        self.showDisabledPaths = False

        self.BB = BoundingBox()

        self.tol = 0

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QCoreApplication.translate('GLWidget',
                                                    string_to_translate))

    def resetAll(self):
        # the wpzero is currently generated "last"
        if self.wpZero > 0:
            GL.glDeleteLists(self.orientation + 1, self.wpZero - self.orientation)
        self.shapes = Shapes([])
        self.wpZero = 0
        self.delete_opt_paths()

        self.posX = 0.0
        self.posY = 0.0
        self.posZ = 0.0
        self.rotX = 0.0
        self.rotY = 0.0
        self.rotZ = 0.0
        self.scale = 1.0

        self.BB = BoundingBox()

        self.update()

    def delete_opt_paths(self):
        if len(self.routearrows) > 0:
            GL.glDeleteLists(self.routearrows[0][2], len(self.routearrows))
            self.routearrows = []

    def addexproutest(self):
        self.expprv = Point3D(g.config.vars.Plane_Coordinates['axis1_start_end'],
                              g.config.vars.Plane_Coordinates['axis2_start_end'],
                              0)

    def addexproute(self, exp_order, layer_nr):
        """
        This function initialises the Arrows of the export route order and its numbers.
        """
        for order in exp_order:
            shape = self.shapes[order]
            st = self.expprv
            en, self.expprv = shape.get_start_end_points_physical()
            en = en.to3D(shape.axis3_start_mill_depth)
            self.expprv = self.expprv.to3D(shape.axis3_mill_depth)

            self.routearrows.append([st, en, -1])

            # TODO self.routetext.append(RouteText(text=("%s,%s" % (layer_nr, shape_nr+1)), startp=en))

    def addexprouteen(self):
        st = self.expprv
        en = Point3D(g.config.vars.Plane_Coordinates['axis1_start_end'],
                     g.config.vars.Plane_Coordinates['axis2_start_end'],
                     0)

        self.routearrows.append([st, en, -1])
        for route in self.routearrows:
            route[2] = self.makeRouteArrowHead(route[0], route[1])

    def contextMenuEvent(self, event):
        if not self.isRotating:
            clicked, offset, _ = self.getClickedDetails(event)
            MyDropDownMenu(self, event.globalPos(), clicked, offset)

    def setXRotation(self, angle):
        self.rotX = self.normalizeAngle(angle)

    def setYRotation(self, angle):
        self.rotY = self.normalizeAngle(angle)

    def setZRotation(self, angle):
        self.rotZ = self.normalizeAngle(angle)

    def normalizeAngle(self, angle):
        return (angle - 180) % -360 + 180

    def updateModifiers(self, event):
        wasRotating = self.isRotating

        super ().updateModifiers (event)

        # short Alt+LeftClick restores rotation to default
        if not wasRotating and self.isRotating:
            self.clickTravelSq = 0.0
        elif wasRotating and not self.isRotating:
            if self.clickTravelSq < 5 * 5:
                self.rotX = 0
                self.rotY = 0
                self.rotZ = 0
                self.update()

    def mousePressEvent(self, event):
        self.updateModifiers(event)

        if self.isPanning or self.isRotating:
            pass

        elif event.button() == Qt.LeftButton:
            clicked, offset, tol = self.getClickedDetails(event)
            xyForZ = {}
            anyHit = False
            for shape in self.shapes:
                hit = False
                z = shape.axis3_start_mill_depth
                if z not in xyForZ:
                    xyForZ[z] = self.determineSelectedPosition(clicked, z, offset)
                hit |= shape.isHit(xyForZ[z], tol)

                if not hit:
                    z = shape.axis3_mill_depth
                    if z not in xyForZ:
                        xyForZ[z] = self.determineSelectedPosition(clicked, z, offset)
                    hit |= shape.isHit(xyForZ[z], tol)

                if self.isMultiSelect and not hit:
                    continue

                anyHit |= hit;

                if self.isMultiSelect and shape.selected:
                    hit = not hit

                if hit != shape.selected:
                    g.window.TreeHandler.updateShapeSelection(shape, hit)

                shape.selected = hit

            # If clicking on empty space without Control pressed, deselect all shapes
            if not anyHit and not self.isMultiSelect:
                for shape in self.shapes:
                    if shape.selected:
                        g.window.TreeHandler.updateShapeSelection(shape, false)

            self.update()

        self._lastPos = event.pos()

    def getClickedDetails(self, event):
        min_side = min(self.frameSize().width(), self.frameSize().height())
        clicked = Point((event.pos().x() - self.frameSize().width() / 2),
                        (event.pos().y() - self.frameSize().height() / 2)) / min_side / self.scale
        offset = Point3D(-self.posX, -self.posY, -self.posZ) / self.scale
        tol = 10 * self.scaleCorr / min_side / self.scale
        return clicked, offset, tol

    def determineSelectedPosition(self, clicked, forZ, offset):
        angleX = -radians(self.rotX)
        angleY = -radians(self.rotY)

        zv = forZ - offset.z
        clickedZ = ((zv + clicked.x * sin(angleY)) / cos(angleY) - clicked.y * sin(angleX)) / cos(angleX)
        sx, sy, sz = self.deRotate(clicked.x, clicked.y, clickedZ)
        return Point(sx + offset.x, - sy - offset.y)  #, sz + offset.z

    def mouseReleaseEvent(self, event):
        self.updateModifiers(event)

    def mouseMoveEvent(self, event):
        self.updateModifiers(event)

        dx = event.pos().x() - self._lastPos.x()
        dy = event.pos().y() - self._lastPos.y()
        self.clickTravelSq += dx * dx + dy * dy

        if self.isRotating:
            if event.buttons() == Qt.LeftButton:
                self.setXRotation(self.rotX - dy / 2)
                self.setYRotation(self.rotY + dx / 2)
            elif event.buttons() == Qt.RightButton:
                self.setXRotation(self.rotX - dy / 2)
                self.setZRotation(self.rotZ + dx / 2)
        elif self.isPanning:
            if event.buttons() == Qt.LeftButton:
                min_side = min(self.frameSize().width(), self.frameSize().height())
                dx, dy, dz = self.deRotate(dx, dy, 0)
                self.posX += dx / min_side
                self.posY += dy / min_side
                self.posZ += dz / min_side

        self._lastPos = event.pos()
        self.update()

    def wheelEvent(self, event):
        min_side = min(self.frameSize().width(), self.frameSize().height())
        x = (event.pos().x() - self.frameSize().width() / 2) / min_side
        y = (event.pos().y() - self.frameSize().height() / 2) / min_side
        s = 1.001 ** event.angleDelta().y()

        x, y, z = self.deRotate(x, y, 0)
        self.posX = (self.posX - x) * s + x
        self.posY = (self.posY - y) * s + y
        self.posZ = (self.posZ - z) * s + z
        self.scale *= s

        self.update()

    def rotate(self, x, y, z):
        angleZ = radians(self.rotZ)
        x, y, z = x*cos(angleZ) - y*sin(angleZ), x*sin(angleZ) + y*cos(angleZ), z
        angleY = radians(self.rotY)
        x, y, z = x*cos(angleY) + z*sin(angleY), y, -x*sin(angleY) + z*cos(angleY)
        angleX = radians(self.rotX)
        return x, y*cos(angleX) - z*sin(angleX), y*sin(angleX) + z*cos(angleX)

    def deRotate(self, x, y, z):
        angleX = -radians(self.rotX)
        x, y, z = x, y*cos(angleX) - z*sin(angleX), y*sin(angleX) + z*cos(angleX)
        angleY = -radians(self.rotY)
        x, y, z = x*cos(angleY) + z*sin(angleY), y, -x*sin(angleY) + z*cos(angleY)
        angleZ = -radians(self.rotZ)
        return x*cos(angleZ) - y*sin(angleZ), x*sin(angleZ) + y*cos(angleZ), z

    def getRotationVectors(self, orgRefVector, toRefVector):
        """
        Generate a rotation matrix such that toRefVector = matrix * orgRefVector
        @param orgRefVector: A 3D unit vector
        @param toRefVector: A 3D unit vector
        @return: 3 vectors such that matrix = [vx; vy; vz]
        """
        # based on:
        # http://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d

        if orgRefVector == toRefVector:
            return Point3D(1, 0, 0), Point3D(0, 1, 0), Point3D(0, 0, 1)

        v = orgRefVector.cross_product(toRefVector)
        mn = (1 - orgRefVector * toRefVector) / v.length_squared()

        vx = Point3D(1, -v.z, v.y) + mn * Point3D(-v.y**2 - v.z**2, v.x * v.y, v.x * v.z)
        vy = Point3D(v.z, 1, -v.x) + mn * Point3D(v.x * v.y, -v.x**2 - v.z**2, v.y * v.z)
        vz = Point3D(-v.y, v.x, 1) + mn * Point3D(v.x * v.z, v.y * v.z, -v.x**2 - v.y**2)

        return vx, vy, vz

    def initializeGL(self):
        logger.debug(self.tr("Using OpenGL version: %s") % GL.glGetString(GL.GL_VERSION).decode("utf-8"))
        self.setClearColor(GLWidget.COLOR_BACKGROUND)

        GL.glEnable(GL.GL_MULTISAMPLE)

        GL.glEnable(GL.GL_POLYGON_SMOOTH)
        GL.glHint(GL.GL_POLYGON_SMOOTH_HINT, GL.GL_NICEST)
        # GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
        GL.glShadeModel(GL.GL_SMOOTH)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_CULL_FACE)
        # GL.glEnable(GL.GL_LIGHTING)
        # GL.glEnable(GL.GL_LIGHT0)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        # GL.glLightfv(GL.GL_LIGHT0, GL.GL_POSITION, (0.5, 5.0, 7.0, 1.0))
        # GL.glEnable(GL.GL_NORMALIZE)

        self.drawOrientationArrows()

    def paintGL(self):
        # The last transformation you specify takes place first.
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glLoadIdentity()
        GL.glRotatef(self.rotX, 1.0, 0.0, 0.0)
        GL.glRotatef(self.rotY, 0.0, 1.0, 0.0)
        GL.glRotatef(self.rotZ, 0.0, 0.0, 1.0)
        GL.glTranslatef(self.posX, self.posY, self.posZ)
        GL.glScalef(self.scale, self.scale, self.scale)
        for shape in self.shapes.selected_iter():
            if not shape.disabled:
                self.setColor(GLWidget.COLOR_STMOVE)
                GL.glCallList(shape.drawStMove)
                self.setColor(GLWidget.COLOR_SELECT)
                GL.glCallList(shape.drawObject)
            elif self.showDisabledPaths:
                self.setColor(GLWidget.COLOR_SELECT_DISABLED)
                GL.glCallList(shape.drawObject)
        for shape in self.shapes.not_selected_iter():
            if not shape.disabled:
                if shape.parentLayer.isBreakLayer():
                    self.setColor(GLWidget.COLOR_BREAK)
                elif shape.cut_cor == 41:
                    self.setColor(GLWidget.COLOR_LEFT)
                elif shape.cut_cor == 42:
                    self.setColor(GLWidget.COLOR_RIGHT)
                else:
                    self.setColor(GLWidget.COLOR_NORMAL)
                GL.glCallList(shape.drawObject)
                if self.showPathDirections:
                    self.setColor(GLWidget.COLOR_STMOVE)
                    GL.glCallList(shape.drawStMove)
            elif self.showDisabledPaths:
                self.setColor(GLWidget.COLOR_NORMAL_DISABLED)
                GL.glCallList(shape.drawObject)

        # optimization route arrows
        self.setColor(GLWidget.COLOR_ROUTE)
        GL.glBegin(GL.GL_LINES)
        for route in self.routearrows:
            start = route[0]
            end = route[1]
            GL.glVertex3f(start.x, -start.y, start.z)
            GL.glVertex3f(end.x, -end.y, end.z)
        GL.glEnd()

        GL.glScalef(self.scaleCorr / self.scale, self.scaleCorr / self.scale, self.scaleCorr / self.scale)
        scaleArrow = self.scale / self.scaleCorr
        for route in self.routearrows:
            # ignore uninitialized arrows
            if route[2] < 0:
                continue
            end = scaleArrow * route[1]
            GL.glTranslatef(end.x, -end.y, end.z)
            GL.glCallList(route[2])
            GL.glTranslatef(-end.x, end.y, -end.z)

        # direction arrows
        for shape in self.shapes:
            if shape.selected and (not shape.disabled or self.showDisabledPaths) or\
               self.showPathDirections and not shape.disabled:
                start, end = shape.get_start_end_points_physical()
                start = scaleArrow * start.to3D(shape.axis3_start_mill_depth)
                end = scaleArrow * end.to3D(shape.axis3_mill_depth)
                GL.glTranslatef(start.x, -start.y, start.z)
                GL.glCallList(shape.drawArrowsDirection[0])
                GL.glTranslatef(-start.x, start.y, -start.z)
                GL.glTranslatef(end.x, -end.y, end.z)
                GL.glCallList(shape.drawArrowsDirection[1])
                GL.glTranslatef(-end.x, end.y, -end.z)

        if self.wpZero > 0:
            GL.glCallList(self.wpZero)
        GL.glTranslatef(-self.posX / self.scaleCorr, -self.posY / self.scaleCorr, -self.posZ / self.scaleCorr)
        GL.glCallList(self.orientation)

    def resizeGL(self, width, height):
        GL.glViewport(0, 0, width, height)
        side = min(width, height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        if width >= height:
            scale_x = width / height
            GL.glOrtho(GLWidget.CAM_LEFT_X * scale_x, GLWidget.CAM_RIGHT_X * scale_x,
                            GLWidget.CAM_BOTTOM_Y, GLWidget.CAM_TOP_Y,
                            GLWidget.CAM_NEAR_Z, GLWidget.CAM_FAR_Z)
        else:
            scale_y = height / width
            GL.glOrtho(GLWidget.CAM_LEFT_X, GLWidget.CAM_RIGHT_X,
                            GLWidget.CAM_BOTTOM_Y * scale_y, GLWidget.CAM_TOP_Y * scale_y,
                            GLWidget.CAM_NEAR_Z, GLWidget.CAM_FAR_Z)
        self.scaleCorr = 400 / side
        GL.glMatrixMode(GL.GL_MODELVIEW)

    def setClearColor(self, c):
        GL.glClearColor(c.redF(), c.greenF(), c.blueF(), c.alphaF())

    def setColor(self, c):
        self.setColorRGBA(c.redF(), c.greenF(), c.blueF(), c.alphaF())

    def setColorRGBA(self, r, g, b, a):
        # GL.glMaterialfv(GL.GL_FRONT, GL.GL_DIFFUSE, (r, g, b, a))
        GL.glColor4f(r, g, b, a)

    def plotAll(self, shapes):
        for shape in shapes:
            self.paint_shape(shape)
            self.shapes.append(shape)
        self.drawWpZero()

    def repaint_shape(self, shape):
        GL.glDeleteLists(shape.drawObject, 4)
        self.paint_shape(shape)

    def paint_shape(self, shape):
        shape.drawObject = self.makeShape(shape)  # 1 object
        shape.stmove = StMove(shape)
        shape.drawStMove = self.makeStMove(shape.stmove)  # 1 object
        shape.drawArrowsDirection = self.makeDirArrows(shape)  # 2 objects

    def makeShape(self, shape):
        genList = GL.glGenLists(1)
        GL.glNewList(genList, GL.GL_COMPILE)

        GL.glBegin(GL.GL_LINES)
        shape.make_path(self.drawHorLine, self.drawVerLine)
        GL.glEnd()

        GL.glEndList()

        self.BB = self.BB.joinBB(shape.BB)


        return genList

    def makeStMove(self, stmove):
        genList = GL.glGenLists(1)
        GL.glNewList(genList, GL.GL_COMPILE)

        GL.glBegin(GL.GL_LINES)
        stmove.make_path(self.drawHorLine, self.drawVerLine)
        GL.glEnd()

        GL.glEndList()

        return genList

    def drawHorLine(self, caller, Ps, Pe):
        GL.glVertex3f(Ps.x, -Ps.y, caller.axis3_start_mill_depth)
        GL.glVertex3f(Pe.x, -Pe.y, caller.axis3_start_mill_depth)
        GL.glVertex3f(Ps.x, -Ps.y, caller.axis3_mill_depth)
        GL.glVertex3f(Pe.x, -Pe.y, caller.axis3_mill_depth)

    def drawVerLine(self, caller, Ps):
        GL.glVertex3f(Ps.x, -Ps.y, caller.axis3_start_mill_depth)
        GL.glVertex3f(Ps.x, -Ps.y, caller.axis3_mill_depth)

    def drawOrientationArrows(self):

        rCone = 0.01
        rCylinder = 0.004
        zTop = 0.05
        zMiddle = 0.02
        zBottom = -0.03
        segments = 20

        arrow = GL.glGenLists(1)
        GL.glNewList(arrow, GL.GL_COMPILE)

        self.drawCone(Point(), rCone, zTop, zMiddle, segments)
        self.drawSolidCircle(Point(), rCone, zMiddle, segments)
        self.drawCylinder(Point(), rCylinder, zMiddle, zBottom, segments)
        self.drawSolidCircle(Point(), rCylinder, zBottom, segments)

        GL.glEndList()

        self.orientation = GL.glGenLists(1)
        GL.glNewList(self.orientation, GL.GL_COMPILE)

        self.setColorRGBA(0.0, 0.0, 1.0, 0.5)
        GL.glCallList(arrow)

        GL.glRotatef(90, 0, 1, 0)
        self.setColorRGBA(1.0, 0.0, 0.0, 0.5)
        GL.glCallList(arrow)

        GL.glRotatef(90, 1, 0, 0)
        self.setColorRGBA(0.0, 1.0, 0.0, 0.5)
        GL.glCallList(arrow)

        GL.glEndList()

    def drawWpZero(self):

        r = 0.02
        segments = 20  # must be a multiple of 4

        self.wpZero = GL.glGenLists(1)
        GL.glNewList(self.wpZero, GL.GL_COMPILE)

        self.setColorRGBA(0.2, 0.2, 0.2, 0.7)
        self.drawSphere(r, segments, segments // 4, segments, segments // 4)

        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glVertex3f(0, 0, 0)
        for i in range(segments // 4 + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r)
            # GL.glNormal3f(0, -1, 0)
            GL.glVertex3f(xy2.x, 0, xy2.y)
        for i in range(segments // 4 + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r)
            # GL.glNormal3f(-1, 0, 0)
            GL.glVertex3f(0, -xy2.y, -xy2.x)
        for i in range(segments // 4 + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r)
            # GL.glNormal3f(0, 0, 1)
            GL.glVertex3f(-xy2.y, xy2.x, 0)
        GL.glEnd()

        self.setColorRGBA(0.6, 0.6, 0.6, 0.5)
        self.drawSphere(r * 1.25, segments, segments, segments, segments)

        GL.glEndList()

    def drawSphere(self, r, lats, mlats, longs, mlongs):
        lats //= 2
        # based on http://www.cburch.com/cs/490/sched/feb8/index.html
        for i in range(mlats):
            lat0 = pi * (-0.5 + i / lats)
            z0 = r * sin(lat0)
            zr0 = r * cos(lat0)
            lat1 = pi * (-0.5 + (i + 1) / lats)
            z1 = r * sin(lat1)
            zr1 = r * cos(lat1)
            GL.glBegin(GL.GL_QUAD_STRIP)
            for j in range(mlongs + 1):
                lng = 2 * pi * j / longs
                x = cos(lng)
                y = sin(lng)

                GL.glNormal3f(x * zr0, y * zr0, z0)
                GL.glVertex3f(x * zr0, y * zr0, z0)
                GL.glNormal3f(x * zr1, y * zr1, z1)
                GL.glVertex3f(x * zr1, y * zr1, z1)
            GL.glEnd()

    def drawSolidCircle(self, origin, r, z, segments):
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        # GL.glNormal3f(0, 0, -1)
        GL.glVertex3f(origin.x, -origin.y, z)
        for i in range(segments + 1):
            ang = -i * 2 * pi / segments
            xy2 = origin.get_arc_point(ang, r)
            GL.glVertex3f(xy2.x, -xy2.y, z)
        GL.glEnd()

    def drawCone(self, origin, r, zTop, zBottom, segments):
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glVertex3f(origin.x, -origin.y, zTop)
        for i in range(segments + 1):
            ang = i * 2 * pi / segments
            xy2 = origin.get_arc_point(ang, r)

            # GL.glNormal3f(xy2.x, -xy2.y, zBottom)
            GL.glVertex3f(xy2.x, -xy2.y, zBottom)
        GL.glEnd()

    def drawCylinder(self, origin, r, zTop, zBottom, segments):
        GL.glBegin(GL.GL_QUAD_STRIP)
        for i in range(segments + 1):
            ang = i * 2 * pi / segments
            xy = origin.get_arc_point(ang, r)

            # GL.glNormal3f(xy.x, -xy.y, 0)
            GL.glVertex3f(xy.x, -xy.y, zTop)
            GL.glVertex3f(xy.x, -xy.y, zBottom)
        GL.glEnd()

    def makeDirArrows(self, shape):
        (start, start_dir), (end, end_dir) = shape.get_start_end_points_physical(None, False)

        startArrow = GL.glGenLists(1)
        GL.glNewList(startArrow, GL.GL_COMPILE)
        self.setColor(GLWidget.COLOR_ENTRY_ARROW)
        self.drawDirArrow(Point3D(), start_dir.to3D(), True)
        GL.glEndList()

        endArrow = GL.glGenLists(1)
        GL.glNewList(endArrow, GL.GL_COMPILE)
        self.setColor(GLWidget.COLOR_EXIT_ARROW)
        self.drawDirArrow(Point3D(), end_dir.to3D(), False)
        GL.glEndList()

        return startArrow, endArrow

    def drawDirArrow(self, origin, direction, startError):
        offset = 0.0 if startError else 0.05
        zMiddle = -0.02 + offset
        zBottom = -0.05 + offset
        rx, ry, rz = self.getRotationVectors(Point3D(0, 0, 1), direction)

        self.drawArrowHead(origin, rx, ry, rz, offset)

        GL.glBegin(GL.GL_LINES)
        zeroMiddle = Point3D(0, 0, zMiddle)
        GL.glVertex3f(zeroMiddle * rx + origin.x, -zeroMiddle * ry - origin.y, zeroMiddle * rz + origin.z)
        zeroBottom = Point3D(0, 0, zBottom)
        GL.glVertex3f(zeroBottom * rx + origin.x, -zeroBottom * ry - origin.y, zeroBottom * rz + origin.z)
        GL.glEnd()

    def makeRouteArrowHead(self, start, end):
        if end == start:
            direction = Point3D(0, 0, 1)
        else:
            direction = (end - start).unit_vector()
        rx, ry, rz = self.getRotationVectors(Point3D(0, 0, 1), direction)

        head = GL.glGenLists(1)
        GL.glNewList(head, GL.GL_COMPILE)
        self.drawArrowHead(Point3D(), rx, ry, rz, 0)
        GL.glEndList()
        return head

    def drawArrowHead(self, origin, rx, ry, rz, offset):
        r = 0.01
        segments = 10
        zTop = 0 + offset
        zBottom = -0.02 + offset

        GL.glBegin(GL.GL_TRIANGLE_FAN)
        zeroTop = Point3D(0, 0, zTop)
        GL.glVertex3f(zeroTop * rx + origin.x, -zeroTop * ry - origin.y, zeroTop * rz + origin.z)
        for i in range(segments + 1):
            ang = i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r).to3D(zBottom)
            GL.glVertex3f(xy2 * rx + origin.x, -xy2 * ry - origin.y, xy2 * rz + origin.z)
        GL.glEnd()

        GL.glBegin(GL.GL_TRIANGLE_FAN)
        zeroBottom = Point3D(0, 0, zBottom)
        GL.glVertex3f(zeroBottom * rx + origin.x, -zeroBottom * ry - origin.y, zeroBottom * rz + origin.z)
        for i in range(segments + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r).to3D(zBottom)
            GL.glVertex3f(xy2 * rx + origin.x, -xy2 * ry - origin.y, xy2 * rz + origin.z)
        GL.glEnd()

    def setShowPathDirections(self, flag):
        self.showPathDirections = flag

    def setShowDisabledPaths(self, flag=True):
        self.showDisabledPaths = flag

    def autoscale(self):
        # TODO currently only works correctly when object is not rotated
        if self.frameSize().width() >= self.frameSize().height():
            aspect_scale_x = self.frameSize().width() / self.frameSize().height()
            aspect_scale_y = 1
        else:
            aspect_scale_x = 1
            aspect_scale_y = self.frameSize().height() / self.frameSize().width()
        dx = self.BB.Pe.x - self.BB.Ps.x
        dy = self.BB.Pe.y - self.BB.Ps.y
        scaleX = (GLWidget.CAM_RIGHT_X - GLWidget.CAM_LEFT_X) * aspect_scale_x / dx if (dx != 0) else 1
        scaleY = (GLWidget.CAM_BOTTOM_Y - GLWidget.CAM_TOP_Y) * aspect_scale_y / dy if (dy != 0) else 1
        self.scale = min(scaleX, scaleY) * 0.95
        self.posX = ((GLWidget.CAM_LEFT_X + GLWidget.CAM_RIGHT_X) * 0.95 * aspect_scale_x
                     - (self.BB.Ps.x + self.BB.Pe.x) * self.scale) / 2
        self.posY = -((GLWidget.CAM_TOP_Y + GLWidget.CAM_BOTTOM_Y) * 0.95 * aspect_scale_y
                      - (self.BB.Pe.y + self.BB.Ps.y) * self.scale) / 2
        self.posZ = 0
        self.update()

    def topView(self):
        self.rotX = 0
        self.rotY = 0
        self.rotZ = 0
        self.update()

    def isometricView(self):
        self.rotX = -22
        self.rotY = -22
        self.rotZ = 0
        self.update()
