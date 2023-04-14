#!/usr/bin/env python3
# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2010-2016
#    Christian Kohlöffel
#    Jean-Paul Schouwstra
#
#   German translation & Python 3.10+ compatibility by Daniel Luginbühl
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

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from copy import copy, deepcopy
from math import degrees, radians

import dxf2gcode.globals.constants as c
import dxf2gcode.globals.globals as g
from dxf2gcode.core.customgcode import CustomGCode
from dxf2gcode.core.entitycontent import EntityContent
from dxf2gcode.core.holegeo import HoleGeo
from dxf2gcode.core.layercontent import LayerContent, Layers, Shapes
from dxf2gcode.core.linegeo import LineGeo
from dxf2gcode.core.point import Point
from dxf2gcode.core.project import Project
from dxf2gcode.dxfimport.importer import ReadDXF
from dxf2gcode.globals.config import MyConfig
from dxf2gcode.globals.helperfunctions import qstr_encode, str_decode, str_encode
from dxf2gcode.globals.logger import LoggerClass
from dxf2gcode.gui.aboutdialog import AboutDialog
from dxf2gcode.gui.configwindow import ConfigWindow
from dxf2gcode.gui.popupdialog import PopUpDialog
from dxf2gcode.gui.treehandling import TreeHandler
from dxf2gcode.postpro.postprocessor import MyPostProcessor
from dxf2gcode.postpro.tspoptimisation import TspOptimization

from PyQt5.QtWidgets import QMainWindow, QGraphicsView, QFileDialog, QApplication, QMessageBox
from PyQt5.QtGui import QSurfaceFormat
from PyQt5 import QtCore


logger = logging.getLogger()

g.folder = os.path.join(os.path.expanduser("~"), ".config/dxf2gcode").replace("\\", "/")


class MainWindow(QMainWindow):

    """
    Main Class
    """

    # Define a QT signal that is emitted when the configuration changes.
    # Connect to this signal if you need to know when the configuration has
    # changed.
    configuration_changed = QtCore.pyqtSignal()

    def __init__(self, app):
        """
        Initialization of the Main window. This is directly called after the
        Logger has been initialized. The Function loads the GUI, creates the
        used Classes and connects the actions to the GUI.
        """
        QMainWindow.__init__(self)

        # Build the configuration window
        self.config_window = ConfigWindow(g.config.makeConfigWidgets(),
                                          g.config.var_dict,
                                          g.config.var_dict.configspec,
                                          self)
        self.config_window.finished.connect(self.updateConfiguration)

        self.app = app
        self.settings = QtCore.QSettings("dxf2gcode", "dxf2gcode")

        self.ui = Ui_MainWindow()

        self.ui.setupUi(self)
        self.showMaximized()

        self.canvas = self.ui.canvas
        if g.config.mode3d:
            self.canvas_scene = self.canvas
        else:
            self.canvas_scene = None

        self.TreeHandler = TreeHandler(self.ui)
        self.configuration_changed.connect(self.TreeHandler.updateConfiguration)

        if sys.version_info[0] == 2:
            error_message = QMessageBox(QMessageBox.Critical, 'ERROR', self.tr("Python version 2 is not supported, please use it with python version 3."))
            sys.exit(error_message.exec_())

        # Load the post-processor configuration and build the post-processor configuration window
        self.MyPostProcessor = MyPostProcessor()
        # If string version_mismatch isn't empty, we popup an error and exit
        if self.MyPostProcessor.version_mismatch:
            error_message = QMessageBox(QMessageBox.Critical, 'Configuration error', self.MyPostProcessor.version_mismatch)
            sys.exit(error_message.exec_())

        self.d2g = Project(self)

        self.createActions()
        self.connectToolbarToConfig()

        self.filename = ""

        self.valuesDXF = None
        self.shapes = Shapes([])
        self.entityRoot = None
        self.layerContents = Layers([])
        self.newNumber = 1

        self.cont_dx = 0.0
        self.cont_dy = 0.0
        self.cont_rotate = 0.0
        self.cont_scale = g.config.vars.Plane_Coordinates['std_scale']
        self.cont_mirrorx = False
        self.cont_mirrory = False

        self.restoreWindowState()

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param: string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QtCore.QCoreApplication.translate('MainWindow',
                                                           string_to_translate))

    def createActions(self):
        """
        Create the actions of the main toolbar.
        @purpose: Links the callbacks to the actions in the menu
        """

        # File
        self.ui.actionOpen.triggered.connect(self.open)
        self.ui.actionReload.triggered.connect(self.reload)
        self.ui.actionSaveProjectAs.triggered.connect(self.saveProject)
        self.ui.actionClose.triggered.connect(self.close)

        # Export
        self.ui.actionOptimizePaths.triggered.connect(self.optimizeTSP)
        self.ui.actionExportShapes.triggered.connect(self.exportShapes)
        self.ui.actionOptimizeAndExportShapes.triggered.connect(self.optimizeAndExportShapes)

        # View
        self.ui.actionShowPathDirections.triggered.connect(self.setShowPathDirections)
        # We need toggled (and not triggered), otherwise the signal is not
        # emitted when state is changed programmatically
        self.ui.actionShowDisabledPaths.toggled.connect(self.setShowDisabledPaths)
        self.ui.actionLiveUpdateExportRoute.toggled.connect(self.liveUpdateExportRoute)
        self.ui.actionDeleteG0Paths.triggered.connect(self.deleteG0Paths)
        self.ui.actionAutoscale.triggered.connect(self.canvas.autoscale)
        if g.config.mode3d:
            self.ui.actionTopView.triggered.connect(self.canvas.topView)
            self.ui.actionIsometricView.triggered.connect(self.canvas.isometricView)

        # Options
        self.ui.actionConfiguration.triggered.connect(self.config_window.show)
        self.ui.actionConfigurationPostprocessor.triggered.connect(self.MyPostProcessor.config_postpro_window.show)
        self.ui.actionTolerances.triggered.connect(self.setTolerances)
        self.ui.actionRotateAll.triggered.connect(self.rotateAll)
        self.ui.actionScaleAll.triggered.connect(self.scaleAll)
        self.ui.actionMirrorAll.triggered.connect(self.MirrorAll)
        self.ui.actionMoveWorkpieceZero.triggered.connect(self.moveWorkpieceZero)
        self.ui.actionSplitLineSegments.toggled.connect(self.d2g.small_reload)
        self.ui.actionAutomaticCutterCompensation.toggled.connect(self.d2g.small_reload)
        self.ui.actionMilling.triggered.connect(self.setMachineTypeToMilling)
        self.ui.actionDragKnife.triggered.connect(self.setMachineTypeToDragKnife)
        self.ui.actionLathe.triggered.connect(self.setMachineTypeToLathe)
        self.ui.actionMillimeters.triggered.connect(self.setMeasurementUnitsToMillimeters)
        self.ui.actionInches.triggered.connect(self.setMeasurementUnitsToInches)

        # Help
        self.ui.actionAbout.triggered.connect(self.about)

    def connectToolbarToConfig(self, project=False, block_signals=True):
        # View
        if not project:
            self.ui.actionShowDisabledPaths.blockSignals(block_signals)  # Don't emit any signal when changing state of the menu entries
            self.ui.actionShowDisabledPaths.setChecked(g.config.vars.General['show_disabled_paths'])
            self.ui.actionShowDisabledPaths.blockSignals(False)
            self.ui.actionLiveUpdateExportRoute.blockSignals(block_signals)
            self.ui.actionLiveUpdateExportRoute.setChecked(g.config.vars.General['live_update_export_route'])
            self.ui.actionLiveUpdateExportRoute.blockSignals(False)

        # Options
        self.ui.actionSplitLineSegments.blockSignals(block_signals)
        self.ui.actionSplitLineSegments.setChecked(g.config.vars.General['split_line_segments'])
        self.ui.actionSplitLineSegments.blockSignals(False)
        self.ui.actionAutomaticCutterCompensation.blockSignals(block_signals)
        self.ui.actionAutomaticCutterCompensation.setChecked(g.config.vars.General['automatic_cutter_compensation'])
        self.ui.actionAutomaticCutterCompensation.blockSignals(False)
        self.updateMachineType()

    def keyPressEvent(self, event):
        """
        Rewritten KeyPressEvent to get other behavior while Shift is pressed.
        @purpose: Changes to ScrollHandDrag while Control pressed
        @param event:    Event Parameters passed to function
        """
        if event.isAutoRepeat():
            return
        if g.config.mode3d:
            self.canvas.updateModifiers(event)
        elif event.key() == QtCore.Qt.Key_Control:
            self.canvas.isMultiSelect = True
        elif event.key() == QtCore.Qt.Key_Shift:
            self.canvas.setDragMode(QGraphicsView.ScrollHandDrag)

    def keyReleaseEvent(self, event):
        """
        Rewritten KeyReleaseEvent to get other behavior while Shift is pressed.
        @purpose: Changes to RubberBandDrag while Control released
        @param event:    Event Parameters passed to function
        """
        if g.config.mode3d:
            self.canvas.updateModifiers(event)
        elif event.key() == QtCore.Qt.Key_Control:
            self.canvas.isMultiSelect = False
        elif event.key() == QtCore.Qt.Key_Shift:
            self.canvas.setDragMode(QGraphicsView.NoDrag)

    def enableToolbarButtons(self, status=True):
        # File
        self.ui.actionReload.setEnabled(status)
        self.ui.actionSaveProjectAs.setEnabled(status)

        # Export
        self.ui.actionOptimizePaths.setEnabled(status)
        self.ui.actionExportShapes.setEnabled(status)
        self.ui.actionOptimizeAndExportShapes.setEnabled(status)

        # View
        self.ui.actionShowPathDirections.setEnabled(status)
        self.ui.actionShowDisabledPaths.setEnabled(status)
        self.ui.actionLiveUpdateExportRoute.setEnabled(status)
        self.ui.actionAutoscale.setEnabled(status)
        if g.config.mode3d:
            self.ui.actionTopView.setEnabled(status)
            self.ui.actionIsometricView.setEnabled(status)

        # Options
        self.ui.actionTolerances.setEnabled(status)
        self.ui.actionRotateAll.setEnabled(status)
        self.ui.actionScaleAll.setEnabled(status)
        self.ui.actionMirrorAll.setEnabled(status)
        self.ui.actionMoveWorkpieceZero.setEnabled(status)

    def deleteG0Paths(self):
        """
        Deletes the optimisation paths from the scene.
        """
        self.setCursor(QtCore.Qt.WaitCursor)
        self.app.processEvents()

        self.canvas_scene.delete_opt_paths()
        self.ui.actionDeleteG0Paths.setEnabled(False)
        self.canvas_scene.update()

        self.unsetCursor()

    def exportShapes(self, status=False, saveas=None):
        """
        This function is called by the menu "Export/Export Shapes". It may open
        a Save Dialog if used without LinuxCNC integration. Otherwise it's
        possible to select multiple postprocessor files, which are located
        in the folder.
        """
        self.setCursor(QtCore.Qt.WaitCursor)
        self.app.processEvents()

        logger.debug(self.tr('Export the enabled shapes'))

        # Get the export order from the QTreeView
        self.TreeHandler.updateExportOrder()
        self.updateExportRoute()

        logger.debug(self.tr("Sorted layers:"))
        for i, layer in enumerate(self.layerContents.non_break_layer_iter()):
            logger.debug("LayerContents[%i] = %s" % (i, layer))

        if not g.config.vars.General['write_to_stdout']:

            # Get the name of the File to export
            if not saveas:
                MyFormats = ""
                for i in range(len(self.MyPostProcessor.output_format)):
                    name = "%s " % (self.MyPostProcessor.output_text[i])
                    format_ = "(*%s);;" % (self.MyPostProcessor.output_format[i])
                    MyFormats = MyFormats + name + format_
                filename = self.showSaveDialog(self.tr('Export to file'), MyFormats, g.config.vars.Paths['output_dir'])
                save_filename = qstr_encode(filename[0])
            else:
                filename = [None, post_pro]
                save_filename = saveas

            # If Cancel was pressed
            if not save_filename:
                self.unsetCursor()
                return

            # If automatic save paths is checked keep it up to date.
            if g.config.vars.Paths['autosave_path']:
                logger.debug("Save output_dir")
                g.config.var_dict["Paths"]["output_dir"]=os.path.dirname(save_filename)
                g.config.update_config()
                g.config.save_varspace()

            (beg, ende) = os.path.split(save_filename)
            (fileBaseName, fileExtension) = os.path.splitext(ende)

            pp_file_nr = 0
            for i in range(len(self.MyPostProcessor.output_format)):
                name = "%s " % (self.MyPostProcessor.output_text[i])
                format_ = "(*%s)" % (self.MyPostProcessor.output_format[i])
                MyFormats = name + format_
                if filename[1] == MyFormats:
                    pp_file_nr = i
            if fileExtension != self.MyPostProcessor.output_format[pp_file_nr]:
                if not QtCore.QFile.exists(save_filename):
                    save_filename += self.MyPostProcessor.output_format[pp_file_nr]

            logger.debug("File Ending => Postprocessor Nr: %i" % (pp_file_nr))
            self.MyPostProcessor.getPostProVars(pp_file_nr)
        else:
            save_filename = ""
            logger.debug("EMC Integration => Postprocessor Nr: %i" % (0))
            self.MyPostProcessor.getPostProVars(0)

        """
        Export will be performed according to LayerContents and their order
        is given in this variable too.
        """

        # Prepare if any exception happens during export
        #try:
        self.MyPostProcessor.exportShapes(self.filename,
                                        save_filename,
                                        self.layerContents)
        #except Exception as e:
        #    logger.error(self.tr('Error exporting shapes: %s') % str (e))

        self.unsetCursor()

        if g.config.vars.General['write_to_stdout']:
            self.close()

    def optimizeAndExportShapes(self, saveas=None, post_pro=None):
        """
        Optimize the tool path, then export the shapes
        """
        self.optimizeTSP()
        self.exportShapes( saveas, post_pro)

    def updateExportRoute(self):
        """
        Update the drawing of the export route
        """
        self.canvas_scene.delete_opt_paths()

        self.canvas_scene.addexproutest()
        for layer in self.layerContents.non_break_layer_iter():
            if len(layer.exp_order) > 0:
                self.canvas_scene.addexproute(layer.exp_order, layer.nr)
        if len(self.canvas_scene.routearrows) > 0:
            self.ui.actionDeleteG0Paths.setEnabled(True)
            self.canvas_scene.addexprouteen()
        self.canvas_scene.update()

    def optimizeTSP(self):
        """
        Method is called to optimize the order of the shapes. This is performed
        by solving the TSP Problem.
        """
        self.setCursor(QtCore.Qt.WaitCursor)
        self.app.processEvents()

        logger.debug(self.tr('Optimize order of enabled shapes per layer'))
        self.canvas_scene.delete_opt_paths()

        # Get the export order from the QTreeView
        logger.debug(self.tr('Updating order according to TreeView'))
        self.TreeHandler.updateExportOrder()
        self.canvas_scene.addexproutest()

        for layerContent in self.layerContents.non_break_layer_iter():
            # Initial values for the Lists to export.
            shapes_to_write = []
            shapes_fixed_order = []
            shapes_st_en_points = []

            # Check all shapes of Layer which shall be exported and create List for it.
            logger.debug(self.tr("Nr. of Shapes %s; Nr. of Shapes in Route %s")
                         % (len(layerContent.shapes), len(layerContent.exp_order)))
            logger.debug(self.tr("Export Order for start: %s") % layerContent.exp_order)

            for shape_nr in range(len(layerContent.exp_order)):
                if not self.shapes[layerContent.exp_order[shape_nr]].send_to_TSP:
                    shapes_fixed_order.append(shape_nr)

                shapes_to_write.append(shape_nr)
                if self.shapes[layerContent.exp_order[shape_nr]].Pocket == True:
                    shapes_st_en_points.append(self.shapes[layerContent.exp_order[shape_nr]].get_start_end_points(PPocket=True))
                else:
                    shapes_st_en_points.append(self.shapes[layerContent.exp_order[shape_nr]].get_start_end_points())

            # Perform Export only if the Number of shapes to export is bigger than 0
            if len(shapes_to_write) > 0:
                # Errechnen der Iterationen
                # Calculate the iterations
                iter_ = min(g.config.vars.Route_Optimisation['max_iterations'], len(shapes_to_write) * 50)

                # Adding the Start and End Points to the List.
                x_st = g.config.vars.Plane_Coordinates['axis1_start_end']
                y_st = g.config.vars.Plane_Coordinates['axis2_start_end']
                start = Point(x_st, y_st)
                ende = Point(x_st, y_st)
                shapes_st_en_points.append([start, ende])

                TSPs = TspOptimization(shapes_st_en_points, shapes_fixed_order)
                logger.info(self.tr("TSP start values initialised for Layer %s") % layerContent.name)
                logger.debug(self.tr("Shapes to write: %s") % shapes_to_write)
                logger.debug(self.tr("Fixed order: %s") % shapes_fixed_order)

                for it_nr in range(iter_ // 50):
                    TSPs.calc_next_iteration()

                logger.debug(self.tr("TSP done with result: %s") % TSPs)

                layerContent.exp_order = [layerContent.exp_order[nr] for nr in TSPs.opt_route[1:]]
                layerContent.optimize()

                self.canvas_scene.addexproute(layerContent.exp_order, layerContent.nr)
                logger.debug(self.tr("New Export Order after TSP: %s") % layerContent.exp_order)
                self.app.processEvents()
            else:
                layerContent.exp_order = []

        if len(self.canvas_scene.routearrows) > 0:
            self.ui.actionDeleteG0Paths.setEnabled(True)
            self.canvas_scene.addexprouteen()

        # Update order in the treeView, according to path calculation done by the TSP
        self.TreeHandler.updateTreeViewOrder()
        self.canvas_scene.update()

        self.unsetCursor()

    def automaticCutterCompensation(self):
        if self.ui.actionAutomaticCutterCompensation.isEnabled() and\
           self.ui.actionAutomaticCutterCompensation.isChecked():
            for layerContent in self.layerContents.non_break_layer_iter():
                if layerContent.automaticCutterCompensationEnabled():
                    new_exp_order = []
                    outside_compensation = True
                    shapes_left = layerContent.shapes
                    while len(shapes_left) > 0:
                        shapes_left = [shape for shape in shapes_left
                                       if not self.ifNotContainedChangeCutCor(shape, shapes_left, outside_compensation, new_exp_order)]
                        outside_compensation = not outside_compensation
                    layerContent.exp_order = list(reversed(new_exp_order))
        self.TreeHandler.updateTreeViewOrder()
        self.canvas_scene.update()

    def ifNotContainedChangeCutCor(self, shape, shapes_left, outside_compensation, new_exp_order):
        if not isinstance(shape, CustomGCode):
            for outerShape in shapes_left:
                if self.isShapeContained(shape, outerShape):
                    return False
            if outside_compensation == shape.cw:
                shape.cut_cor = 41
            else:
                shape.cut_cor = 42
            self.canvas_scene.repaint_shape(shape)
        new_exp_order.append(shape.nr)
        return True

    def isShapeContained(self, shape, outerShape):
        return shape != outerShape and not \
            isinstance(outerShape, CustomGCode) and\
            shape.BB.iscontained(outerShape.BB)

    def showSaveDialog(self, title, MyFormats, save_to_folder):
        """
        This function is called by the menu "Export/Export Shapes" of the main toolbar.
        It creates the selection dialog for the exporter
        @return: Returns the filename of the selected file.
        """

        (beg, ende) = os.path.split(self.filename)
        (fileBaseName, fileExtension) = os.path.splitext(ende)

        default_name = os.path.join(save_to_folder, fileBaseName)
        logger.debug("default_name: %s", default_name)

        selected_filter = self.MyPostProcessor.output_format[0]
        filename = QFileDialog.getSaveFileName(self,
                                   title, default_name,
                                   MyFormats, selected_filter)


        logger.debug(filename)
        # If there is something to load then call the load function callback
        if filename:
            #filename = qstr_encode(filename)
            logger.info(self.tr("File: %s selected") % filename[0])
            logger.info(self.tr("Filter: %s selected") % filename[1])
            logger.info("<a href='%s'>%s</a>" % (filename[0], filename[0]))
            return filename
        else:
            return False

    def about(self):
        """
        This function is called by the menu "Help/About" of the main toolbar and
        creates the About Window
        """

        message = self.tr("<html>"
                          "<h2><center>You are using</center></h2>"
                          "<body bgcolor="
                          "<center><img src=':images/dxf2gcode_logo.png' border='1' color='white'></center></body>"
                          "<h2>Version:</h2>"
                          "<body>%s: %s<br>"
                          "Last change: %s<br>"
                          "Changed by: %s<br></body>"
                          "<h2>Where to get help:</h2>"
                          "For more information and updates, "
                          "please visit "
                          "<a href='http://sourceforge.net/projects/dxf2gcode/'>http://sourceforge.net/projects/dxf2gcode/</a><br>"
                          "For any questions on how to use dxf2gcode please use the "
                          "<a href='https://www.ltspiceusers.ch/forums/english-section.67/'>https://www.ltspiceusers.ch/forums/english-section.67/</a><br>"
                          "To log bugs, or request features please use the "
                          "<a href='http://sourceforge.net/p/dxf2gcode/tickets/'>issue tracking system</a><br>"
                          "<h2>License and copyright:</h2>"
                          "<body>This program is written in Python and is published under the "
                          "<a href='http://www.gnu.org/licenses/'>GNU GPLv3 license.</a><br>"
                          "</body></html>") % (c.VERSION, c.REVISION, c.DATE, c.AUTHOR)

        AboutDialog(title=self.tr("About DXF2GCODE"), message=message)

    def setShowPathDirections(self):
        """
        This function is called by the menu "Show all path directions" of the
        main and forwards the call to Canvas.setShow_path_direction()
        """
        flag = self.ui.actionShowPathDirections.isChecked()
        self.canvas.setShowPathDirections(flag)
        self.canvas_scene.update()

    def setShowDisabledPaths(self):
        """
        This function is called by the menu "Show disabled paths" of the
        main and forwards the call to Canvas.setShow_disabled_paths()
        """
        flag = self.ui.actionShowDisabledPaths.isChecked()
        self.canvas_scene.setShowDisabledPaths(flag)
        self.canvas_scene.update()

    def liveUpdateExportRoute(self):
        """
        This function is called by the menu "Live update tool path" of the
        main and forwards the call to TreeHandler.setUpdateExportRoute()
        """
        flag = self.ui.actionLiveUpdateExportRoute.isChecked()
        self.TreeHandler.setLiveUpdateExportRoute(flag)

    def setTolerances(self):
        title = self.tr('Contour tolerances')
        units = "in" if g.config.metric == 0 else "mm"
        label = [self.tr("Tolerance for common points [%s]:") % units,
                 self.tr("Tolerance for curve fitting [%s]:") % units]
        value = [g.config.point_tolerance,
                 g.config.fitting_tolerance]
        wtype = ["lineEdit", "lineEdit"]

        logger.debug(self.tr("set Tolerances"))
        SetTolDialog = PopUpDialog(title, label, value, wtype)

        if SetTolDialog.result is None:
            return

        g.config.point_tolerance = float(SetTolDialog.result[0])
        g.config.fitting_tolerance = float(SetTolDialog.result[1])

        self.d2g.reload()  # set tolerances requires a complete reload



    def MirrorAll(self):
        title = self.tr('Mirror all X / Y-Axis')
        label = [self.tr("Mirror all on X-Axis:"), self.tr("Mirror all on Y-Axis:")]
        value = [self.cont_mirrorx, self.cont_mirrory]
        wtype = ["checkBox","checkBox"]
        MirrorDialog = PopUpDialog(title, label, value, wtype)

        if MirrorDialog.result is None:
            return

        self.cont_mirrorx = MirrorDialog.result[0]
        self.cont_mirrory = MirrorDialog.result[1]

        self.entityRoot.mirrorx = self.cont_mirrorx
        self.entityRoot.mirrory = self.cont_mirrory

        self.d2g.small_reload()

    def scaleAll(self):
        title = self.tr('Scale Contour')
        label = [self.tr("Scale Contour by factor:")]
        value = [self.cont_scale]
        wtype = ["lineEdit"]
        ScaEntDialog = PopUpDialog(title, label, value, wtype)

        if ScaEntDialog.result is None:
            return

        self.cont_scale = float(ScaEntDialog.result[0])
        self.entityRoot.sca = self.cont_scale

        self.d2g.small_reload()

    def rotateAll(self):
        title = self.tr('Rotate Contour')
        # TODO should we support radians for drawing unit non metric?
        label = [self.tr("Rotate Contour by deg:")]
        value = [degrees(self.cont_rotate)]
        wtype = ["lineEdit"]
        RotEntDialog = PopUpDialog(title, label, value, wtype)

        if RotEntDialog.result is None:
            return

        self.cont_rotate = radians(float(RotEntDialog.result[0]))
        self.entityRoot.rot = self.cont_rotate

        self.d2g.small_reload()

    def moveWorkpieceZero(self):
        """
        This function is called when the Option=>Move WP Zero Menu is clicked.
        """
        title = self.tr('Workpiece zero offset')
        units = "[in]" if g.config.metric == 0 else "[mm]"
        label = [self.tr("Offset %s axis %s:") % (g.config.vars.Axis_letters['ax1_letter'], units),
                 self.tr("Offset %s axis %s:") % (g.config.vars.Axis_letters['ax2_letter'], units)]
        value = [self.cont_dx, self.cont_dy]
        wtype = ["lineEdit","lineEdit"]
        MoveWpzDialog = PopUpDialog(title, label, value, wtype, True)

        if MoveWpzDialog.result is None:
            return

        if MoveWpzDialog.result == 'Auto':
            minx = sys.float_info.max
            miny = sys.float_info.max
            for shape in self.shapes:
                if not shape.isDisabled():
                    minx = min(minx, shape.BB.Ps.x)
                    miny = min(miny, shape.BB.Ps.y)
            if not (minx == sys.float_info.max or miny == sys.float_info.max):
                self.cont_dx = self.entityRoot.p0.x - minx
                self.cont_dy = self.entityRoot.p0.y - miny
        else:
            self.cont_dx = float(MoveWpzDialog.result[0])
            self.cont_dy = float(MoveWpzDialog.result[1])

        if self.entityRoot.p0.x != self.cont_dx or self.entityRoot.p0.y != self.cont_dy:
            self.entityRoot.p0.x = self.cont_dx
            self.entityRoot.p0.y = self.cont_dy

            self.d2g.small_reload()
        else:
            logger.info(self.tr("No differences found. Ergo, workpiece zero is not moved"))

    def setMachineTypeToMilling(self):
        g.config.machine_type = 'milling'
        self.updateMachineType()
        self.d2g.small_reload()

    def setMachineTypeToDragKnife(self):
        g.config.machine_type = 'drag_knife'
        self.updateMachineType()
        self.d2g.small_reload()

    def setMachineTypeToLathe(self):
        g.config.machine_type = 'lathe'
        self.updateMachineType()
        self.d2g.small_reload()

    def updateMachineType(self):
        if g.config.machine_type == 'milling':
            self.ui.actionAutomaticCutterCompensation.setEnabled(True)
            self.ui.actionMilling.setChecked(True)
            self.ui.actionDragKnife.setChecked(False)
            self.ui.actionLathe.setChecked(False)
            self.ui.label_9.setText(self.tr("Z Infeed depth"))
        elif g.config.machine_type == 'lathe':
            self.ui.actionAutomaticCutterCompensation.setEnabled(False)
            self.ui.actionMilling.setChecked(False)
            self.ui.actionDragKnife.setChecked(False)
            self.ui.actionLathe.setChecked(True)
            self.ui.label_9.setText(self.tr("No Z-Axis for lathe"))
        elif g.config.machine_type == "drag_knife":
            self.ui.actionAutomaticCutterCompensation.setEnabled(False)
            self.ui.actionMilling.setChecked(False)
            self.ui.actionDragKnife.setChecked(True)
            self.ui.actionLathe.setChecked(False)
            self.ui.label_9.setText(self.tr("Z Drag depth"))

    def setMeasurementUnitsToMillimeters(self):
        self.setMeasurementUnits(1)

    def setMeasurementUnitsToInches(self):
        self.setMeasurementUnits(0)

    def setMeasurementUnits(self, metric, refresh_ui=False):
        """
        Change the measurement units used in DXF file.
        Helps if dxf2gcode was unable to detect the correct units.
        """

        self.ui.menu_Measurement_units.setEnabled(True)
        self.ui.actionMillimeters.setChecked(metric == 1)
        self.ui.actionInches.setChecked(metric == 0)

        if (g.config.metric != metric) or refresh_ui:
            if metric == 0:
                logger.info(self.tr("Drawing units: inches"))
                distance = self.tr("[in]")
                speed = self.tr("[IPM]")
            else:
                logger.info(self.tr("Drawing units: millimeters"))
                distance = self.tr("[mm]")
                speed = self.tr("[mm/min]")
            self.ui.unitLabel_3.setText(distance)
            self.ui.unitLabel_4.setText(distance)
            self.ui.unitLabel_5.setText(distance)
            self.ui.unitLabel_6.setText(distance)
            self.ui.unitLabel_7.setText(distance)
            self.ui.unitLabel_8.setText(speed)
            self.ui.unitLabel_9.setText(speed)

        if g.config.metric != metric:
            for layerContent in self.layerContents:
                layerContent.changeMeasuringUnits(g.config.metric, metric)
            g.config.metric = metric
            g.config.update_tool_values()
            self.configuration_changed.emit()
            self.TreeHandler.updateToolParameters()

    def open(self):
        """
        This function is called by the menu "File/Load File" of the main toolbar.
        It creates the file selection dialog and calls the load function to
        load the selected file.
        """

        self.OpenFileDialog(self.tr("Open file"))

        # If there is something to load then call the load function callback
        if self.filename:
            self.cont_dx = 0.0
            self.cont_dy = 0.0
            self.cont_rotate = 0.0
            self.cont_scale =  g.config.vars.Plane_Coordinates['std_scale']
            self.cont_mirrorx = False
            self.cont_mirrory = False

            self.load()

    def OpenFileDialog(self, title):
        self.filename, _ = QFileDialog. getOpenFileName(self,
                                           title,
                                           g.config.vars.Paths['import_dir'],
                                           self.tr("All supported files (*.dxf *.DXF *.ps *.PS *.pdf *.PDF *%s);;"
                                                   "DXF files (*.dxf *.DXF);;"
                                                   "PS files (*.ps *.PS);;"
                                                   "PDF files (*.pdf *.PDF);;"
                                                   "Project files (*%s);;"
                                                   "All types (*.*)") % (c.PROJECT_EXTENSION, c.PROJECT_EXTENSION))


        # If there is something to load then call the load function callback
        if not(self.filename):
            return

        # If automatic save paths is checked keep it up to date.
        if g.config.vars.Paths['autosave_path']:
            logger.debug("Save import_dir")
            g.config.var_dict["Paths"]["import_dir"] = os.path.dirname(self.filename)
            g.config.update_config()
            g.config.save_varspace()

        self.filename = qstr_encode(self.filename)
        logger.info(self.tr("File: %s selected") % self.filename)




    def load(self, plot=True):
        """
        Loads the file given by self.filename.  Also calls the command to
        make the plot.
        @param plot: if it should plot
        """
        if not QtCore.QFile.exists(self.filename):
            logger.info(self.tr("Cannot locate file: %s") % self.filename)
            self.OpenFileDialog(self.tr("Manually open file: %s") % self.filename)
            if not self.filename:
                return False  # cancelled

        self.setCursor(QtCore.Qt.WaitCursor)
        self.setWindowTitle("DXF2GCODE - [%s]" % self.filename)
        self.canvas.resetAll()
        self.app.processEvents()

        (name, ext) = os.path.splitext(self.filename)

        if ext.lower() == c.PROJECT_EXTENSION:
            self.loadProject(self.filename)
            return True  # kill this load operation - we opened a new one

        if ext.lower() == ".ps" or ext.lower() == ".pdf":
            # in case of PDF the two stage conversion will take place
            # as pstoedit is not able to directly convert PDF->DXF
            # Stages:
            #     1) PDF->PS (using pdftops - not pdf2ps!)
            #     2) PS->DXF (using pstoedit)
            if ext.lower() == ".pdf":
                logger.info(self.tr("Converting {0} to {1}").format("PDF", "PS"))

                # Create temporary file which will be read by the program
                tmp_filename = os.path.join(tempfile.gettempdir(), 'dxf2gcode_temp.ps')

                pdftops_cmd = g.config.vars.Filters['pdftops_cmd']
                pdftops_opt = g.config.vars.Filters['pdftops_opt']
                if len(pdftops_opt) == 1 and len(pdftops_opt[0]) == 0:
                    pdftops_opt = list()
                ps_filename = os.path.normcase(self.filename)
                cmd = [('%s' % pdftops_cmd)] + pdftops_opt + [('%s' % ps_filename),
                                                              ('%s' % os.path.normcase(tmp_filename))]
                logger.debug(cmd)
                self.filename = os.path.normcase(tmp_filename)
                try:
                    rv = subprocess.call(cmd)
                    if rv != 0:
                        self.unsetCursor()
                        QMessageBox.critical(self,
                                             "ERROR",
                                             self.tr(
                                                 "Command:\n{0}\nreturned error code: {1}").format(' '.join(cmd), rv))
                        return True

                except OSError as e:
                    logger.error(e.strerror)
                    self.unsetCursor()
                    QMessageBox.critical(self,
                                         "ERROR",
                                         self.tr(
                                             "Please make sure you have installed {0}, and configured it in the config file.").format("pdftops"))
                    return True

            logger.info(self.tr("Converting {0} to {1}").format("PS", "DXF"))

            # Create temporary file which will be read by the program
            tmp_filename = os.path.join(tempfile.gettempdir(), 'dxf2gcode_temp.dxf')

            pstoedit_cmd = g.config.vars.Filters['pstoedit_cmd']
            pstoedit_opt = g.config.vars.Filters['pstoedit_opt']
            if len(pstoedit_opt) == 1 and len(pstoedit_opt[0]) == 0:
                pstoedit_opt = list()
            ps_filename = os.path.normcase(self.filename)
            cmd = [('%s' % pstoedit_cmd)] + pstoedit_opt + [('%s' % ps_filename), ('%s' % os.path.normcase(tmp_filename))]
            logger.debug(cmd)
            self.filename = os.path.normcase(tmp_filename)
            try:
                rv = subprocess.call(cmd)
                if rv != 0:
                    self.unsetCursor()
                    QMessageBox.critical(self,
                                         "ERROR",
                                         self.tr(
                                             "Command:\n{0}\nreturned error code: {1}").format(' '.join(cmd), rv))
                    return True

            except OSError as e:
                logger.error(e.strerror)
                self.unsetCursor()
                QMessageBox.critical(self,
                                     "ERROR",
                                     self.tr("Please make sure you have installed {0}, and configured it in the config file.").format("pstoedit"))
                return True
            # If the return code was non-zero it raises a
            # subprocess.CalledProcessError.
            # subprocess.check_output()

        logger.info(self.tr('Loading file: %s') % self.filename)

        self.valuesDXF = ReadDXF(self.filename)

        # Output the information in the text window
        logger.info(self.tr('Loaded layers: %s') % len(self.valuesDXF.layers))
        logger.info(self.tr('Loaded blocks: %s') % len(self.valuesDXF.blocks.Entities))
        for i in range(len(self.valuesDXF.blocks.Entities)):
            layers = self.valuesDXF.blocks.Entities[i].get_used_layers()
            logger.info(self.tr('Block %i includes %i Geometries, reduced to %i Contours, used layers: %s')
                        % (i, len(self.valuesDXF.blocks.Entities[i].geo), len(self.valuesDXF.blocks.Entities[i].cont), layers))
        layers = self.valuesDXF.entities.get_used_layers()
        insert_nr = self.valuesDXF.entities.get_insert_nr()
        logger.info(self.tr('Loaded %i entity geometries; reduced to %i contours; used layers: %s; number of inserts %i')
                    % (len(self.valuesDXF.entities.geo), len(self.valuesDXF.entities.cont), layers, insert_nr))

        self.setMeasurementUnits(g.config.metric, True)

        self.makeShapes()
        if plot:
            self.plot()
        return True

    def plot(self):
        # Populate the treeViews
        self.TreeHandler.buildEntitiesTree(self.entityRoot)
        self.TreeHandler.buildLayerTree(self.layerContents)

        # Paint the canvas
        if not g.config.mode3d:
            self.canvas_scene = MyGraphicsScene()
            self.canvas.setScene(self.canvas_scene)

        self.canvas_scene.plotAll(self.shapes)
        self.setShowPathDirections()
        self.setShowDisabledPaths()
        self.liveUpdateExportRoute()

        if not g.config.mode3d:
            self.canvas.show()
            self.canvas.setFocus()
        self.canvas.autoscale()

        # After all is plotted enable the Menu entities
        self.enableToolbarButtons()

        self.automaticCutterCompensation()

        self.unsetCursor()

    def reload(self):
        """
        This function is called by the menu "File/Reload File" of the main toolbar.
        It reloads the previously loaded file (if any)
        """
        if self.filename:
            logger.info(self.tr("Reloading file: %s") % self.filename)
            self.load()

    def makeShapes(self):
        self.entityRoot = EntityContent(nr=0, name='Entities', parent=None,
                                        p0=Point(self.cont_dx, self.cont_dy), pb=Point(),
                                        sca=[self.cont_scale, self.cont_scale, self.cont_scale], rot=self.cont_rotate,
                                        mirrorx = self.cont_mirrorx, mirrory = self.cont_mirrory)

        self.layerContents = Layers([])
        self.shapes = Shapes([])

        self.makeEntityShapes(self.entityRoot)

        for layerContent in self.layerContents:
            layerContent.overrideDefaults()
        self.layerContents.sort(key=lambda x: x.nr)
        self.newNumber = len(self.shapes)

    def makeEntityShapes(self, parent, layerNr=-1):
        """
        Instance is called prior to plotting the shapes. It creates
        all shape classes which are plotted into the canvas.

        @param parent: The parent of a shape is always an Entity. It may be the root
        or, if it is a Block, this is the Block.
        """
        if parent.name == "Entities":
            entities = self.valuesDXF.entities
        else:
            ent_nr = self.valuesDXF.Get_Block_Nr(parent.name)
            entities = self.valuesDXF.blocks.Entities[ent_nr]

        # Assigning the geometries in the variables geos & contours in cont
        ent_geos = entities.geo

        # Loop for the number of contours
        for cont in entities.cont:
            # Query if it is in the contour of an insert or of a block
            if ent_geos[cont.order[0][0]].Typ == "Insert":
                ent_geo = ent_geos[cont.order[0][0]]

                # Assign the base point for the block
                new_ent_nr = self.valuesDXF.Get_Block_Nr(ent_geo.BlockName)
                new_entities = self.valuesDXF.blocks.Entities[new_ent_nr]
                pb = new_entities.basep

                # Scaling, etc. assign the block
                p0 = ent_geos[cont.order[0][0]].Point
                sca = ent_geos[cont.order[0][0]].Scale
                rot = ent_geos[cont.order[0][0]].rot
                #mirrorx = False #ent_geos[cont.order[0][0]].mirrorx
                #mirrory = False #ent_geos[cont.order[0][0]].mirrory

                # Creating the new Entitie Contents for the insert
                newEntityContent = EntityContent(nr=0,
                                                 name=ent_geo.BlockName,
                                                 parent=parent,
                                                 p0=p0,
                                                 pb=pb,
                                                 sca=sca,
                                                 rot=rot)

                                                #mirrorx=mirrorx,
                                                #mirrory=mirrory

                parent.append(newEntityContent)

                self.makeEntityShapes(newEntityContent, ent_geo.Layer_Nr)

            else:
                # Loop for the number of geometries
                tmp_shape = Shape(len(self.shapes),
                                  (True if cont.closed else False),
                                  parent)

                for ent_geo_nr in range(len(cont.order)):
                    ent_geo = ent_geos[cont.order[ent_geo_nr][0]]
                    if cont.order[ent_geo_nr][1]:
                        ent_geo.geo.reverse()
                        for geo in ent_geo.geo:
                            geo = copy(geo)
                            geo.reverse()
                            self.append_geo_to_shape(tmp_shape, geo)
                        ent_geo.geo.reverse()
                    else:
                        for geo in ent_geo.geo:
                            self.append_geo_to_shape(tmp_shape, copy(geo))

                if len(tmp_shape.geos) > 0:
                    # All shapes have to be CW direction.
                    tmp_shape.AnalyseAndOptimize()

                    self.shapes.append(tmp_shape)
                    if g.config.vars.Import_Parameters['insert_at_block_layer'] and layerNr != -1:
                        self.addtoLayerContents(tmp_shape, layerNr)
                    else:
                        self.addtoLayerContents(tmp_shape, ent_geo.Layer_Nr)
                    parent.append(tmp_shape)

                    if not g.config.mode3d:
                        # Connect the shapeSelectionChanged and enableDisableShape signals to our treeView,
                        # so that selections of the shapes are reflected on the treeView
                        tmp_shape.setSelectionChangedCallback(self.TreeHandler.updateShapeSelection)
                        tmp_shape.setEnableDisableCallback(self.TreeHandler.updateShapeEnabling)

    def append_geo_to_shape(self, shape, geo):
        if -1e-5 <= geo.length < 1e-5:  # TODO adjust import for this
            return

        if self.ui.actionSplitLineSegments.isChecked():
            if isinstance(geo, LineGeo):
                diff = (geo.Pe - geo.Ps) / 2.0
                geo_b = deepcopy(geo)
                geo_a = deepcopy(geo)
                geo_b.Pe -= diff
                geo_a.Ps += diff
                shape.append(geo_b)
                shape.append(geo_a)
            else:
                shape.append(geo)
        else:
            shape.append(geo)

        if isinstance(geo, HoleGeo):
            shape.type = 'Hole'
            shape.closed = True  # TODO adjust import for holes?
            if g.config.machine_type == 'drag_knife':
                shape.disabled = True
                shape.allowedToChange = False

    def addtoLayerContents(self, shape, lay_nr):
        # Check if the layer already exists and add shape if it is.
        for LayCon in self.layerContents:
            if LayCon.nr == lay_nr:
                LayCon.shapes.append(shape)
                shape.parentLayer = LayCon
                return

        # If the Layer does not exist create a new one.
        LayerName = self.valuesDXF.layers[lay_nr].name
        self.layerContents.append(LayerContent(lay_nr, LayerName, [shape]))
        shape.parentLayer = self.layerContents[-1]

    def updateConfiguration(self, result):
        """
        Some modification occured in the configuration window, we need to save these changes into the config file.
        Once done, the signal configuration_changed is emitted, so that anyone interested in this information can connect to this signal.
        """
        if result == ConfigWindow.Applied or result == ConfigWindow.Accepted:
            # Write the configuration into the config file (config.cfg)
            g.config.save_varspace()
            # Rebuild the readonly configuration structure
            g.config.update_config()

            # Assign changes to the menus (if no change occured, nothing
            # happens / otherwise QT emits a signal for the menu entry that has changed)
            self.connectToolbarToConfig(block_signals=False)

            # Inform about the changes into the configuration
            self.configuration_changed.emit()

    def loadProject(self, filename):
        """
        Load all variables from file
        """
        # since Py3 has no longer execfile -  we need to open it manually
        file_ = open(filename, 'r')
        str_ = file_.read()
        file_.close()
        self.d2g.load(str_)

    def saveProject(self):
        """
        Save all variables to file
        """
        prj_filename = self.showSaveDialog(self.tr('Save project to file'),
                                           "Project files (*%s)" % c.PROJECT_EXTENSION,
                                           g.config.vars.Paths['project_dir'])

        save_prj_filename = qstr_encode(prj_filename[0])

        # If Cancel was pressed
        if not save_prj_filename:
            return

        # If automatic save paths is checked keep it up to date.
        if g.config.vars.Paths['autosave_path']:
            logger.debug("Save project_dir")
            g.config.var_dict["Paths"]["project_dir"] = os.path.dirname(prj_filename[0])
            g.config.update_config()
            g.config.save_varspace()

        (beg, ende) = os.path.split(save_prj_filename)
        (fileBaseName, fileExtension) = os.path.splitext(ende)

        if fileExtension != c.PROJECT_EXTENSION:
            if not QtCore.QFile.exists(save_prj_filename):
                save_prj_filename += c.PROJECT_EXTENSION

        pyCode = self.d2g.export()
        try:
            # File open and write
            f = open(save_prj_filename, "w")
            f.write(str_encode(pyCode))
            f.close()
            logger.info(self.tr("Save project to FILE was successful"))
        except IOError:
            QMessageBox.warning(g.window,
                                self.tr("Warning during Save Project As"),
                                self.tr("Cannot Save the File"))

    def closeEvent(self, e):
        logger.debug(self.tr("Closing"))
        self.saveWindowState()
        e.accept()

    def restoreWindowState(self):
        self.settings.beginGroup("MainWindow")
        geometry = self.settings.value("geometry")
        state = self.settings.value("state")
        self.settings.endGroup()
        if (geometry is not None) and (state is not None):
            self.restoreGeometry(geometry)
            self.restoreState(state)

    def saveWindowState(self):
        self.settings.beginGroup("MainWindow")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("state", self.saveState())
        self.settings.endGroup()


if __name__ == "__main__":
    """
    The main function which is executed after program start.
    """
    Log = LoggerClass(logger)

    g.config = MyConfig()
    Log.set_console_handler_loglevel()

    if not g.config.vars.Logging['logfile']:
        Log.add_window_logger()
    else:
        Log.add_file_logger()

    app = QApplication(sys.argv)

    # Get local language and install if available.
    locale = QtCore.QLocale.system().name()
    logger.debug("locale: %s" % locale)
    translator = QtCore.QTranslator()
    #logger.debug(os.getcwd())
    #logger.debug(os.path.dirname(os.path.abspath(__file__)))
    #logger.debug(translator.load("dxf2gcode_" + locale, "./i18n"))
    #logger.debug(translator.load("dxf2gcode_" + locale, os.path.join(os.path.dirname(os.path.abspath(__file__)),"i18n")))

    if translator.load("dxf2gcode_" + locale, "./i18n"):
        app.installTranslator(translator)
    elif translator.load("dxf2gcode_" + locale, os.path.join(os.path.dirname(os.path.abspath(__file__)),"i18n")):
        app.installTranslator(translator)
    elif translator.load("dxf2gcode_" + locale, "/usr/share/dxf2gcode/i18n"):
        app.installTranslator(translator)


    # If string version_mismatch isn't empty, we popup an error and exit
    if g.config.version_mismatch:
        error_message = QMessageBox(QMessageBox.Critical, 'Configuration error', g.config.version_mismatch)
        sys.exit(error_message.exec_())

    # Delay imports - needs to be done after logger and config initialization; and before the main window
    from dxf2gcode_ui5 import Ui_MainWindow

    if g.config.mode3d:
        from dxf2gcode.core.shape import Shape
        # multi-sampling has been introduced in PyQt5
        fmt = QSurfaceFormat()
        fmt.setSamples(4)
        QSurfaceFormat.setDefaultFormat(fmt)
    else:
        from dxf2gcode.gui.canvas2d import MyGraphicsScene
        from dxf2gcode.gui.canvas2d import ShapeGUI as Shape
    window = MainWindow(app)
    g.window = window
    Log.add_window_logger(window.ui.messageBox)

    # command line options
    parser = argparse.ArgumentParser()

    parser.add_argument("filename", nargs="?")

    #    parser.add_argument("-f", "--file", dest = "filename",
    #                        help = "read data from FILENAME")
    parser.add_argument("-e", "--export", dest="export_filename",
                        help="export data to FILENAME")
    parser.add_argument("-p", "--postpro", dest="post_pro",
                        help="Post Processor to use")
    parser.add_argument("-o", "--optimize", action="store_true",
                        dest="optimize", help="optimize before export")
    parser.add_argument("-q", "--quiet", action="store_true",
                        dest="quiet", help="no GUI")
    #    parser.add_option("-v", "--verbose",
    #                      action = "store_true", dest = "verbose")
    options = parser.parse_args()
    g.quiet = options.quiet

    # (options, args) = parser.parse_args()
    logger.debug("Started with following options:\n%s" % parser)

    if not options.quiet:
        window.show()

    if options.filename is not None:
        window.filename = str_decode(options.filename)
        window.load()

    if options.export_filename is not None:
        window.exportShapes(None, options.export_filename)

    if not options.quiet:
        # It's exec_ because exec is a reserved word in Python
        sys.exit(app.exec_())
