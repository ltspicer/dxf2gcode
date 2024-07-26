# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2012-2015
#    Xavier Izard
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
This class is intended to deal with the drawing (.dxf) structure.
It has the following functions:
- populate the entities treeView and the layers treeView
- allow selection of shapes from any treeView and show the
  selection on the graphic view
- allow to enable/disable shapes from any treeView
- reflects into the treeView the changes that occurs on the graphic view
- set export order using drag & drop

@purpose: display tree structure of the .dxf file, select,
          enable and set export order of the shapes
"""

from __future__ import absolute_import

from math import degrees
import logging

import dxf2gcode.globals.globals as g

from dxf2gcode.core.shape import Shape
from dxf2gcode.core.entitycontent import EntityContent
from dxf2gcode.core.customgcode import CustomGCode
from dxf2gcode.gui.treeview import MyStandardItemModel

from dxf2gcode.globals.helperfunctions import toInt, toFloat

import dxf2gcode.globals.constants as c
from PyQt5.QtWidgets import QAction, QMenu, QWidget, QAbstractItemView, QTreeView
from PyQt5.QtCore import QItemSelectionModel, QItemSelection
from PyQt5.QtGui import QStandardItem, QIcon, QPixmap, QStandardItemModel, QPalette
from PyQt5 import QtCore
isValid = lambda data: data
toPyObject = lambda data: data


class QVariantShape(QtCore.QVariant):
    """
    Wrapper is needed for PyQt5 since this version does not accept to add a QGraphisItem
     directly to a QStandardItem
    """
    def __init__(self, shapeobj):
        self.shapeobj = shapeobj


logger = logging.getLogger("Gui.TreeHandling")

# defines some arbitrary types for the objects stored into the treeView.
# These types will eg help us to find which kind of data is stored
# in the element received from a click() event
ENTITY_OBJECT = QtCore.Qt.UserRole + 1  # For storing refs to the entities elements (entities_list)
LAYER_OBJECT = QtCore.Qt.UserRole + 2  # For storing refs to the layers elements (layers_list)
SHAPE_OBJECT = QtCore.Qt.UserRole + 3  # For storing refs to the shape elements (entities_list & layers_list)
CUSTOM_GCODE_OBJECT = QtCore.Qt.UserRole + 4  # For storing refs to the custom gcode elements (layers_list)

PATH_OPTIMISATION_COL = 3  # Column that corresponds to TSP enable checkbox


class TreeHandler(QWidget):
    """
    Class to handle both QTreeView :  entitiesTreeView (for blocks, and the tree of blocks) and layersShapesTreeView (for layers and shapes)
    """

    def __init__(self, ui):
        """
        Standard method to initialize the class
        @param ui: the GUI
        """
        QWidget.__init__(self)
        self.ui = ui

        # Used to store previous values in order to enable/disable text
        self.palette = self.ui.zRetractionArealLineEdit.palette()
        self.clearToolsParameters()

        # Layers & Shapes TreeView
        self.layer_item_model = None
        self.layers_list = None
        self.auto_update_export_order = False
        self.ui.layersShapesTreeView.setExportOrderUpdateCallback(self.prepareExportOrderUpdate)
        self.ui.layersShapesTreeView.setSelectionCallback(self.actionOnSelectionChange)  # pass the callback function to the QTreeView
        self.ui.layersShapesTreeView.setKeyPressEventCallback(self.actionOnKeyPress)
        self.ui.layersShapesTreeView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ui.layersShapesTreeView.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.ui.layersGoUpPushButton.clicked.connect(self.ui.layersShapesTreeView.moveUpCurrentItem)
        self.ui.layersGoDownPushButton.clicked.connect(self.ui.layersShapesTreeView.moveDownCurrentItem)

        # Load the tools from the config file to the tool selection combobox
        for tool in g.config.vars.Tool_Parameters:
            self.ui.toolDiameterComboBox.addItem(tool)

        # Select the first tool in the list and update the tools diameter, ... accordingly
        self.ui.toolDiameterComboBox.setCurrentIndex(0)
        self.toolUpdate()

        # The layer/shape which is currently displayed in the parameters box
        self.display_tool_layer = None
        self.display_tool_shape = None

        # Don't change this line, the signal _must_ be "activated" (only activates on user action) and _not_ "currentIndexChanged" (activates programmatically and on user action)
        self.ui.toolDiameterComboBox.activated[str].connect(self.toolUpdate)

        self.ui.zRetractionArealLineEdit.editingFinished.connect(self.toolParameterzRetractionArealUpdate)
        self.ui.zSafetyMarginLineEdit.editingFinished.connect(self.toolParameterzSafetyMarginUpdate)
        self.ui.zInitialMillDepthLineEdit.editingFinished.connect(self.toolParameterzInitialMillDepthUpdate)
        self.ui.zInfeedDepthLineEdit.editingFinished.connect(self.toolParameterzInfeedDepthUpdate)
        self.ui.zFinalMillDepthLineEdit.editingFinished.connect(self.toolParameterzFinalMillDepthUpdate)
        self.ui.g1FeedXYLineEdit.editingFinished.connect(self.toolParameterg1FeedXYUpdate)
        self.ui.g1FeedZLineEdit.editingFinished.connect(self.toolParameterg1FeedZUpdate)
        
        # Entities TreeView
        self.entity_item_model = None
        self.entities_list = None
        self.ui.entitiesTreeView.setSelectionCallback(self.actionOnSelectionChange)  # pass the callback function to the QTreeView
        self.ui.entitiesTreeView.setKeyPressEventCallback(self.actionOnKeyPress)
        self.ui.entitiesTreeView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ui.entitiesTreeView.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.ui.blocksCollapsePushButton.clicked.connect(self.expandToDepth0)
        self.ui.blocksExpandPushButton.clicked.connect(self.ui.entitiesTreeView.expandAll)

        # Build the contextual menu (mouse right click)
        self.context_menu = QMenu(self)
        self.context_menu.addAction(QAction("Select all", self, triggered=self.ui.layersShapesTreeView.selectAll))
        self.context_menu.addAction(QAction("Deselect all", self, triggered=self.ui.layersShapesTreeView.clearSelection))
        self.context_menu.addSeparator()
        self.context_menu.addAction(QAction("Enable selection", self, triggered=self.enableSelectedItems))
        self.context_menu.addAction(QAction("Disable selection", self, triggered=self.disableSelectedItems))
        self.context_menu.addSeparator()
        self.context_menu.addAction(QAction("Optimize route for selection", self, triggered=self.optimizeRouteForSelectedItems))
        self.context_menu.addAction(QAction("Don't opti. route for selection", self, triggered=self.doNotOptimizeRouteForSelectedItems))
        self.context_menu.addSeparator()
        self.context_menu.addAction(QAction("Remove custom GCode", self, triggered=self.removeCustomGCodeSelected))

        self.sub_menu = QMenu("Add custom GCode ...", self)
        # Save the exact name of the action, as is defined in the config file. Later on we use it to identify the action
        for custom_action in g.config.vars.Custom_Actions:
            menu_action = self.sub_menu.addAction(custom_action.replace('_', ' '))
            menu_action.setData(custom_action)

        self.context_menu.addMenu(self.sub_menu)

        # Right click menu
        self.ui.layersShapesTreeView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.layersShapesTreeView.customContextMenuRequested.connect(self.displayContextMenu)

        # Not used for now, so hide them
        self.ui.startAtXLabel.hide()
        self.ui.startAtYLabel.hide()
        self.ui.unitLabel_1.hide()
        self.ui.unitLabel_2.hide()
        self.ui.startAtXLineEdit.hide()
        self.ui.startAtYLineEdit.hide()

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param: string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QtCore.QCoreApplication.translate('TreeHandler',
                                                           string_to_translate))

    def updateConfiguration(self):
        """
        This function should be called each time the configuration changes. It updates tools and custom actions in the treeView
        If a tool or a custom action disapear from the configuration, it is removed from the treeview
        """
        # Load the tools from the config file to the tool selection combobox
        #self.ui.layersShapesTreeView.clearSelection()
        self.ui.toolDiameterComboBox.blockSignals(True)
        default_tool = 1 # Tool 1 normally always exists
        current_tool = self.ui.toolDiameterComboBox.currentText()
        self.ui.toolDiameterComboBox.clear()
        for tool in g.config.vars.Tool_Parameters:
            self.ui.toolDiameterComboBox.addItem(tool)
        self.ui.toolDiameterComboBox.blockSignals(False)

        # Load the custom gcode names from the config file
        self.sub_menu.clear()
        for custom_action in g.config.vars.Custom_Actions:
            menu_action = self.sub_menu.addAction(custom_action.replace('_', ' '))
            menu_action.setData(custom_action)

        # update the items (if a tool or a custom_action disapeared from config file, we need to remove it in the treeview too)
        i = 0
        if self.layer_item_model: #  this is not set until buildLayerTree() is called
            i = self.layer_item_model.rowCount(QtCore.QModelIndex())

        while i > 0:
            i -= 1
            layer_item_index = self.layer_item_model.index(i, 0)

            if isValid(layer_item_index.data(LAYER_OBJECT)):
                real_layer = toPyObject(layer_item_index.data(LAYER_OBJECT))

                update_drawing = False
                if real_layer is not None and str(real_layer.tool_nr) not in g.config.vars.Tool_Parameters:
                    # The tool used for this layer doesn't exist anymore, we are going to replace it with the first tool
                    logger.warning("Tool {0} used for \"{1}\" layer doesn't exist anymore in the configuration ; using tool {2} instead".format(real_layer.tool_nr, real_layer.name, default_tool))
                    # Update the layer's tool and repaint
                    real_layer.tool_nr = default_tool # Tool 1 normally always exists
                    update_drawing = True

                if real_layer is not None\
                    and (real_layer.tool_diameter != g.config.vars.Tool_Parameters[str(real_layer.tool_nr)]['diameter']\
                      or real_layer.speed != g.config.vars.Tool_Parameters[str(real_layer.tool_nr)]['speed']\
                      or real_layer.start_radius != g.config.vars.Tool_Parameters[str(real_layer.tool_nr)]['start_radius']):
                    # The tool used for this layer exists, but its definition has changed, we need to update the layer
                    logger.warning("Tool {0} used for \"{1}\" layer has changed, updating layer's data".format(real_layer.tool_nr, real_layer.name))
                    real_layer.tool_diameter = g.config.vars.Tool_Parameters[str(real_layer.tool_nr)]['diameter']
                    real_layer.speed = g.config.vars.Tool_Parameters[str(real_layer.tool_nr)]['speed']
                    real_layer.start_radius = g.config.vars.Tool_Parameters[str(real_layer.tool_nr)]['start_radius']
                    update_drawing = True

                if update_drawing and g.window:
                    for shape in real_layer.shapes:
                        if isinstance(shape, Shape):
                            # Only repaint _real_ shapes (and not the custom GCode for example)
                            g.window.canvas_scene.repaint_shape(shape)
                    g.window.canvas_scene.update()

                # Assign the export order for the shapes of the layer "real_layer"
                for j in range(self.layer_item_model.rowCount(layer_item_index)):
                    shape_item_index = self.layer_item_model.index(j, 0, layer_item_index)

                    if isValid(shape_item_index.data(CUSTOM_GCODE_OBJECT)):
                        real_custom_action = toPyObject(shape_item_index.data(CUSTOM_GCODE_OBJECT))
                        if real_custom_action is not None and real_custom_action.name not in g.config.vars.Custom_Actions:
                            logger.warning("Custom action \"{0}\" used for \"{1}\" layer doesn't exist anymore in the configuration, removing it".format(real_custom_action.name, real_layer.name))
                            self.removeCustomGCode(shape_item_index)

        # Reselect the previous tool and update the tool display for the _selected_ layers
        tool_index = self.ui.toolDiameterComboBox.findText(current_tool)
        logger.debug("reselecting tool : " + current_tool)
        if tool_index >= 0:
            self.ui.toolDiameterComboBox.setCurrentIndex(tool_index)
        else:
            tool_index = self.ui.toolDiameterComboBox.findText(default_tool)
            self.ui.toolDiameterComboBox.setCurrentIndex(tool_index)
        self.toolUpdate()


    def displayContextMenu(self, position):
        """
        Function used to display a right click context menu
        @param position: position of the cursor within the treeView widget
        """
        selected_action = self.context_menu.exec_(self.ui.layersShapesTreeView.mapToGlobal(position))

        if selected_action and isValid(selected_action.data()):
            # contextual menu selection concerns a custom gcode
            custom_gcode_name = toPyObject(selected_action.data())

            self.addCustomGCodeAfter(custom_gcode_name)

    def expandToDepth0(self):
        """
        Slot used to expand the entities treeView up to depth 0
        """
        self.ui.entitiesTreeView.expandToDepth(0)

    def buildLayerTree(self, layers_list):
        """
        This method populates the Layers QTreeView with all the elements contained into the layers_list
        Method must be called each time a new .dxf file is loaded.
        options
        @param layers_list: list of the layers and shapes (created in the main)
        """
        self.layers_list = layers_list
        if self.layer_item_model:
            self.layer_item_model.clear()  # Remove any existing item_model
        self.layer_item_model = MyStandardItemModel()  # This is the container for the data (QStandardItemModel)
        self.layer_item_model.setHorizontalHeaderItem(0, QStandardItem(self.tr("[en]")))
        self.layer_item_model.setHorizontalHeaderItem(1, QStandardItem(self.tr("Name")))
        self.layer_item_model.setHorizontalHeaderItem(2, QStandardItem(self.tr("Nr")))
        self.layer_item_model.setHorizontalHeaderItem(3, QStandardItem(self.tr("Optimal path")))
        modele_root_element = self.layer_item_model.invisibleRootItem()  # Root element of our tree

        for layer in layers_list:
            icon = QIcon()
            icon.addPixmap(QPixmap(":/images/layer.png"))
            checkbox_element = QStandardItem(icon, "")
            checkbox_element.setData(QtCore.QVariant(layer), LAYER_OBJECT)  # store a ref in our treeView element
            modele_element = QStandardItem(layer.name)
            nbr_element = QStandardItem()
            optimise_element = QStandardItem()
            modele_root_element.appendRow([checkbox_element, modele_element, nbr_element, optimise_element])

            parent_item = modele_root_element.child(modele_root_element.rowCount() - 1, 0)
            containsChecked = False
            containsUnchecked = False
            for shape in layer.shapes:
                if isinstance(shape, CustomGCode):
                    self.AddCustomGCodeRowLayer(shape, parent_item)
                else:
                    self.AddShapeRowLayer(shape, parent_item)
                if shape.isDisabled():
                    containsUnchecked = True
                else:
                    containsChecked = True

            checkbox_element.setCheckState(self.getCheckState(containsChecked, containsUnchecked))
            checkbox_element.setFlags(QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            modele_element.setFlags(QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            nbr_element.setFlags(QtCore.Qt.ItemIsEnabled)
            optimise_element.setFlags(QtCore.Qt.ItemIsEnabled)

        # Signal to get events when a checkbox state changes (enable or disable shapes)
        self.layer_item_model.itemChanged.connect(self.on_itemChanged)

        self.ui.layersShapesTreeView.setModel(self.layer_item_model)  # Affect our model to the GUI TreeView, in order to display it

        self.ui.layersShapesTreeView.expandAll()

        self.ui.layersShapesTreeView.setDragDropMode(QTreeView.InternalMove)
        # self.ui.layersShapesTreeView.setDefaultDropAction(QtCore.Qt.MoveAction)
        # self.ui.layersShapesTreeView.setDragDropOverwriteMode(True)
        self.ui.layersShapesTreeView.setDropIndicatorShown(True)
        self.ui.layersShapesTreeView.setAcceptDrops(True)
        self.ui.layersShapesTreeView.setDragEnabled(True)

        for i in range(4):
            self.ui.layersShapesTreeView.resizeColumnToContents(i)

    def AddShapeRowLayer(self, shape, parent_item):
        icon = QIcon()
        icon.addPixmap(QPixmap(":/images/shape.png"))
        item_col_0 = QStandardItem(icon, "")
        item_col_0.setData(QVariantShape(shape), SHAPE_OBJECT)  # store a ref in our treeView element
        item_col_1 = QStandardItem(shape.type)
        item_col_2 = QStandardItem(str(shape.nr))
        item_col_3 = QStandardItem()
        parent_item.appendRow([item_col_0, item_col_1, item_col_2, item_col_3])

        # Deal with the checkboxes (shape enabled or disabled / send shape to TSP optimizer)
        item_col_0.setCheckState(QtCore.Qt.Unchecked if shape.isDisabled() else QtCore.Qt.Checked)
        item_col_3.setCheckState(QtCore.Qt.Checked if shape.isToolPathOptimized() else QtCore.Qt.Unchecked)

        flags = QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsSelectable
        if shape.allowedToChange:
            flags |= QtCore.Qt.ItemIsEnabled
        item_col_0.setFlags(flags | QtCore.Qt.ItemIsUserCheckable)
        item_col_1.setFlags(flags)
        item_col_2.setFlags(flags)
        item_col_3.setFlags(flags | QtCore.Qt.ItemIsUserCheckable)

    def AddCustomGCodeRowLayer(self, custom_gcode, parent_item, push_row=None):
        icon = QIcon()
        icon.addPixmap(QPixmap(":/images/custom.png"))
        item_col_0 = QStandardItem(icon, "")  # will only display a checkbox + an icon that will never be disabled
        item_col_0.setData(QtCore.QVariant(custom_gcode), CUSTOM_GCODE_OBJECT)  # store a ref to the custom gcode in our treeView element
        item_col_1 = QStandardItem(custom_gcode.name)
        item_col_2 = QStandardItem(str(custom_gcode.nr))
        item_col_3 = QStandardItem()
        if push_row:
            parent_item.insertRow(push_row, [item_col_0, item_col_1, item_col_2, item_col_3])
        else:
            parent_item.appendRow([item_col_0, item_col_1, item_col_2, item_col_3])

        # Deal with the checkboxes (shape enabled or disabled / send shape to TSP optimizer)
        item_col_0.setCheckState(QtCore.Qt.Unchecked if custom_gcode.isDisabled() else QtCore.Qt.Checked)

        flags = QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        item_col_0.setFlags(flags | QtCore.Qt.ItemIsUserCheckable)
        item_col_1.setFlags(flags)
        item_col_2.setFlags(flags)
        item_col_3.setFlags(flags)

    def buildEntitiesTree(self, entities_list):
        """
        This method populates the Entities (blocks) QTreeView with
        all the elements contained in the entities_list
        Method must be called each time a new .dxf file is loaded.
        options
        @param entities_list: list of the layers and shapes (created in the main)
        """

        self.entities_list = entities_list
        if self.entity_item_model:
            self.entity_item_model.clear()  # Remove any existing item_model
        self.entity_item_model = QStandardItemModel()
        self.entity_item_model.setHorizontalHeaderItem(0, QStandardItem(self.tr("[en]")))
        self.entity_item_model.setHorizontalHeaderItem(1, QStandardItem(self.tr("Name")))
        self.entity_item_model.setHorizontalHeaderItem(2, QStandardItem(self.tr("Nr")))
        self.entity_item_model.setHorizontalHeaderItem(3, QStandardItem(self.tr("Type")))
        self.entity_item_model.setHorizontalHeaderItem(4, QStandardItem(self.tr("Base point")))
        self.entity_item_model.setHorizontalHeaderItem(5, QStandardItem(self.tr("Scale")))
        self.entity_item_model.setHorizontalHeaderItem(6, QStandardItem(self.tr("Rotation")))
        modele_root_element = self.entity_item_model.invisibleRootItem()

        self.buildEntitiesSubTree(modele_root_element, entities_list)

        # Signal to get events when a checkbox state changes (enable or disable shapes)
        self.entity_item_model.itemChanged.connect(self.on_itemChanged)

        self.ui.entitiesTreeView.setModel(self.entity_item_model)

        self.ui.entitiesTreeView.expandToDepth(0)

        for i in range(6):
            self.ui.entitiesTreeView.resizeColumnToContents(i)

    def buildEntitiesSubTree(self, elements_model, elements_list):
        """
        This method is called (possibly recursively) to populate the
        Entities treeView. It is not intended to be called directly,
        use buildEntitiesTree() function instead.
        options
        @param elements_model: the treeView model (used to store the data, see QT docs)
        @param elements_list: either a list of entities, or a shape
        @return (containsChecked, containsUnchecked) indicating whether the subtree contains checked and/or unchecked elements
        """
        containsChecked = False
        containsUnchecked = False
        if isinstance(elements_list, list):
            # We got a list
            for element in elements_list:
                (checked, unchecked) = self.addEntitySubTree(elements_model, element)
                containsChecked = containsChecked or checked
                containsUnchecked = containsUnchecked or unchecked
        else:
            # Unique element (shape)
            element = elements_list
            containsChecked, containsUnchecked = self.addEntitySubTree(elements_model, element)
        return containsChecked, containsUnchecked

    def addEntitySubTree(self, elements_model, element):
        """
        This method populates a row of the Entities treeView. It is
        not intended to be called directly, use buildEntitiesTree()
        function instead.
        options
        @param elements_model: the treeView model (used to store the data, see QT docs)
        @param element: the Entity or Shape element
        @return (containsChecked, containsUnchecked) indicating whether the subtree contains checked and/or unchecked elements
        """
        containsChecked = False
        containsUnchecked = False
        item_col_0 = None
        if isinstance(element, EntityContent):
            icon = QIcon()
            icon.addPixmap(QPixmap(":/images/blocks.png"))
            item_col_0 = QStandardItem(icon, "")  # will only display a checkbox + an icon that will never be disabled
            item_col_0.setData(QtCore.QVariant(element), ENTITY_OBJECT)  # store a ref in our treeView element
            item_col_1 = QStandardItem(element.name)
            item_col_2 = QStandardItem(str(element.nr))
            item_col_3 = QStandardItem("Entity")
            item_col_4 = QStandardItem(str(element.p0))
            item_col_5 = QStandardItem(str(element.sca))
            item_col_6 = QStandardItem(str(round(degrees(element.rot), 3)))  # convert the angle into degrees with 3 digit after the decimal point
            elements_model.appendRow([item_col_0, item_col_1, item_col_2, item_col_3, item_col_4, item_col_5, item_col_6])

            for sub_element in element.children:
                (checked, unchecked) = self.buildEntitiesSubTree(item_col_0, sub_element)
                containsChecked = containsChecked or checked
                containsUnchecked = containsUnchecked or unchecked

            flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled

        elif isinstance(element, Shape):
            icon = QIcon()
            icon.addPixmap(QPixmap(":/images/shape.png"), QIcon.Normal, QIcon.Off)
            item_col_0 = QStandardItem(icon, "")  # will only display a checkbox + an icon that will never be disabled
            item_col_0.setData(QVariantShape(element), SHAPE_OBJECT)  # store a ref in our treeView element
            item_col_1 = QStandardItem(element.type)
            item_col_2 = QStandardItem(str(element.nr))
            item_col_3 = QStandardItem(element.type)
            item_col_4 = QStandardItem()
            item_col_5 = QStandardItem()
            item_col_6 = QStandardItem()
            elements_model.appendRow([item_col_0, item_col_1, item_col_2, item_col_3, item_col_4, item_col_5, item_col_6])
            if element.isDisabled():
                containsUnchecked = True
            else:
                containsChecked = True

            flags = QtCore.Qt.ItemIsSelectable
            if element.allowedToChange:
                flags |= QtCore.Qt.ItemIsEnabled

        item_col_0.setCheckState(self.getCheckState(containsChecked, containsUnchecked))

        item_col_0.setFlags(flags | QtCore.Qt.ItemIsUserCheckable)
        item_col_1.setFlags(flags)
        item_col_2.setFlags(flags)
        item_col_3.setFlags(flags)
        item_col_4.setFlags(flags)
        item_col_5.setFlags(flags)
        item_col_6.setFlags(flags)

        return (containsChecked, containsUnchecked)

    def getCheckState(self, containsChecked, containsUnchecked):
        if containsChecked:
            if containsUnchecked:
                return QtCore.Qt.PartiallyChecked
            else:
                return QtCore.Qt.Checked
        else:
            return QtCore.Qt.Unchecked

    def updateExportOrder(self, includeDisableds=False):
        """
        Update the layers_list order to reflect the TreeView order.
        This function must be called before generating the GCode
        (export function). Export will be performed in the order of the
        structure self.LayerContents of the main. Each layer contains
        some shapes, and the export order of the shapes is set by
        populating the exp_order[] list with the shapes reference number
        for each layer (eg exp_order = [5, 3, 2, 4, 0, 1] for layer 0,
        exp_order = [5, 3, 7] for layer 1, ...)
        options
        """

        i = self.layer_item_model.rowCount(QtCore.QModelIndex())
        while i > 0:
            i -= 1
            layer_item_index = self.layer_item_model.index(i, 0)

            if isValid(layer_item_index.data(LAYER_OBJECT)):
                real_layer = toPyObject(layer_item_index.data(LAYER_OBJECT))
                self.layers_list.remove(real_layer)  # Remove the layer from its original position
                self.layers_list.insert(0, real_layer)  # and insert it at the beginning of the layer's list

                real_layer.exp_order = []  # Clear the current export order
                real_layer.exp_order_complete = []  # Clear the current export order

                # Assign the export order for the shapes of the layer "real_layer"
                for j in range(self.layer_item_model.rowCount(layer_item_index)):
                    shape_item_index = self.layer_item_model.index(j, 0, layer_item_index)

                    real_shape = None
                    if isValid(shape_item_index.data(SHAPE_OBJECT)):
                        real_shape = toPyObject(shape_item_index.data(SHAPE_OBJECT)).shapeobj
                        if not real_shape.isDisabled() or includeDisableds:
                            real_layer.exp_order.append(real_shape.nr)  # Create the export order list with the real and unique shapes numbers (eg [25, 22, 30, 4, 1, 5])

                    if isValid(shape_item_index.data(CUSTOM_GCODE_OBJECT)):
                        real_shape = toPyObject(shape_item_index.data(CUSTOM_GCODE_OBJECT))

                    if real_shape and (not real_shape.isDisabled() or includeDisableds):
                        real_layer.exp_order_complete.append(real_layer.shapes.index(real_shape))  # Create the export order list with the shapes & custom gcode numbers (eg [5, 3, 2, 4, 0, 1])

    def updateTreeViewOrder(self):
        """
        Update the Layer TreeView order according to the exp_order list
        of each layer. This function should be called after running the
        TSP path otimizer
        """

        i = self.layer_item_model.rowCount(QtCore.QModelIndex())
        while i > 0:
            i -= 1
            layer_item_index = self.layer_item_model.index(i, 0)
            layer_item = self.layer_item_model.itemFromIndex(layer_item_index)

            if isValid(layer_item_index.data(LAYER_OBJECT)):
                real_layer = toPyObject(layer_item_index.data(LAYER_OBJECT))

                # for shape_nr in real_layer.exp_order[::-1]:  # reverse order and prepend if we want to insert optimized shape before fixed shapes
                for shape_nr in real_layer.exp_order:
                    for j in range(self.layer_item_model.rowCount(layer_item_index)):
                        shape_item_index = self.layer_item_model.index(j, 0, layer_item_index)

                        if isValid(shape_item_index.data(SHAPE_OBJECT)):
                            real_shape = toPyObject(shape_item_index.data(SHAPE_OBJECT)).shapeobj

                            if real_shape and real_shape.nr == shape_nr and (real_shape.send_to_TSP or g.config.vars.Route_Optimisation['TSP_shape_order'] == 'CONSTRAIN_ORDER_ONLY'):
                                # Shape number "shape_nr" found in the treeView and Shape is movable => moving it to its new position
                                item_to_be_moved = layer_item.takeRow(j)
                                layer_item.appendRow(item_to_be_moved)

                                break

    def columnsSelectDeselect(self, selection_model, item_index, select):
        """
        columnsSelectDeselect()
        """
        if select:
            # Select the matching shape in the list.
            selection_model.select(item_index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        else:
            # Unselect the matching shape in the list.
            selection_model.select(item_index, QItemSelectionModel.Deselect | QItemSelectionModel.Rows)

    def updateShapeSelection(self, shape, select):
        """
        This method is a "slot" (callback) called from the main when the
        selection changes on the graphic view. It aims to update the
        treeView selection according to the graphic view.
        Note: in order to avoid signal loops, all selection signals are
        blocked when updating the selections in the treeViews
        options
        @param shape: the Shape whose selection has changed
        @param select: whether the Shape has been selected (True) or deselected (False)
        """
        # Layer treeView
        item_index = self.findLayerItemIndexFromShape(shape)
        selection_model = self.ui.layersShapesTreeView.selectionModel()  # Get the selection model of the QTreeView

        if item_index:
            # we found the matching index for the shape in our layers treeView model
            self.ui.layersShapesTreeView.blockSignals(True)  # Avoid signal loops (we dont want the treeView to re-emit selectionChanged signal)
            self.columnsSelectDeselect(selection_model, item_index, select)
            self.ui.layersShapesTreeView.setCurrentIndex(item_index)
            self.ui.layersShapesTreeView.blockSignals(False)

        # Entities treeView
        item_index = self.findEntityItemIndexFromShape(shape)
        selection_model = self.ui.entitiesTreeView.selectionModel()  # Get the selection model of the QTreeView

        if item_index:
            # we found the matching index for the shape in our entities treeView model
            self.ui.entitiesTreeView.blockSignals(True)  # Avoid signal loops (we dont want the treeView to re-emit selectionChanged signal)
            self.columnsSelectDeselect(selection_model, item_index, select)
            self.ui.entitiesTreeView.setCurrentIndex(item_index)
            self.ui.entitiesTreeView.blockSignals(False)

        # Update the tool parameters fields
        self.clearToolsParameters()
        self.displayToolParametersForItem(shape.parentLayer, shape)

    def updateShapeEnabling(self, shape, enable):
        """
        This method is a "slot" (callback) called from the main when the
        shapes are enabled or disabled on the graphic view.
        It aims to update the treeView checkboxes according to the
        graphic view.
        Note: in order to avoid signal loops, all selection signals are
        blocked when updating the checkboxes in the treeViews
        options
        @param shape: the Shape whose enabling has changed
        @param enable: whether the Shape has been enabled (True) or disabled (False)
        """
        # Layer treeView
        item_index = self.findLayerItemIndexFromShape(shape)

        if item_index:
            # we found the matching index for the shape in our treeView model
            item = item_index.model().itemFromIndex(item_index)

            self.layer_item_model.blockSignals(True)  # Avoid signal loops (we dont want the treeView to emit itemChanged signal)
            if enable:
                # Select the matching shape in the list
                self.updateCheckboxOfItem(item, QtCore.Qt.Checked)

            else:
                # deselect the matching shape in the list
                self.updateCheckboxOfItem(item, QtCore.Qt.Unchecked)

            self.layer_item_model.blockSignals(False)
            self.ui.layersShapesTreeView.update(item_index)  # update the treeList drawing
            self.traverseParentsAndUpdateEnableDisable(self.layer_item_model, item_index)  # update the parents checkboxes

            if self.auto_update_export_order:
                # update export order and thus export drawing
                self.prepareExportOrderUpdate()

        #Entities treeView
        item_index = self.findEntityItemIndexFromShape(shape)

        if item_index:
            # we found the matching index for the shape in our treeView model
            item = item_index.model().itemFromIndex(item_index)

            self.entity_item_model.blockSignals(True)  # Avoid signal loops (we dont want the treeView to emit itemChanged signal)
            if enable:
                # Select the matching shape in the list
                self.updateCheckboxOfItem(item, QtCore.Qt.Checked)

            else:
                # deselect the matching shape in the list
                self.updateCheckboxOfItem(item, QtCore.Qt.Unchecked)

            self.entity_item_model.blockSignals(False)
            self.ui.entitiesTreeView.update(item_index)  # update the treeList drawing
            self.traverseParentsAndUpdateEnableDisable(self.entity_item_model, item_index)  # update the parents checkboxes

    def findLayerItemIndexFromShape(self, shape):
        """
        Find internal layers treeView reference (item index) matching a
        "real" shape (ie a ShapeClass instance)
        options
        @param shape: the real shape (ShapeClass instance)
        @return: the found item index (can be None)
        """
        return self.traverseChildrenAndFindShape(self.layer_item_model, QtCore.QModelIndex(), shape)

    def findEntityItemIndexFromShape(self, shape):
        """
        Find internal entities treeView reference (item index) matching
        a "real" shape (ie a ShapeClass instance)
        options
        @param shape: the real shape (ShapeClass instance)
        @return: the found item index (can be None)
        """
        return self.traverseChildrenAndFindShape(self.entity_item_model, QtCore.QModelIndex(), shape)

    def traverseChildrenAndFindShape(self, item_model, item_index, shape):
        """
        This method is used by the findLayerItemIndexFromShape() and
        findEntityItemIndexFromShape() function in order to find a
        reference from a layer. It traverses the QT model and compares
        each item data with the shape passed as parameter. When found,
        the reference is returned
        options
        @param item_model: the treeView model (used to store the data, see QT docs)
        @param item_index: the initial model index (QModelIndex) in the tree (all children of this index are scanned)
        @param shape: the real shape (ShapeClass instance)
        @return: the found item index
        """
        for i in range(item_model.rowCount(item_index)):
            sub_item_index = item_model.index(i, 0, item_index)

            if isValid(sub_item_index.data(SHAPE_OBJECT)):
                real_item = toPyObject(sub_item_index.data(SHAPE_OBJECT)).shapeobj
                if shape == real_item:
                    return sub_item_index

            if item_model.hasChildren(sub_item_index):
                found_item_index = self.traverseChildrenAndFindShape(item_model, sub_item_index, shape)
                if found_item_index:
                    return found_item_index

    def traverseChildrenAndSelect(self, item_model, item_index, state):
        """
        This method is used internally to select/deselect all children
        of a given entity (eg to select all the shapes of a given layer
        when the user has selected a layer)
        options
        @param item_model: the treeView model (used to store the data, see QT docs)
        @param item_index: the initial model index (QModelIndex) in the tree (all children of this index are scanned)
        @param select: whether to select (True) or not (False)
        """
        for i in range(item_model.rowCount(item_index)):
            sub_item_index = item_model.index(i, 0, item_index)

            if item_model.hasChildren(sub_item_index):
                self.traverseChildrenAndSelect(item_model, sub_item_index, state)
            else:
                element = sub_item_index.model().itemFromIndex(sub_item_index)
                if element:
                    if element.data(SHAPE_OBJECT):
                        toPyObject(element.data(SHAPE_OBJECT)).shapeobj.setSelected (state)
                    elif element.data(CUSTOM_GCODE_OBJECT):
                        toPyObject(element.data(CUSTOM_GCODE_OBJECT)).setSelected (state)

    def traverseChildrenAndEnableDisable(self, item_model, item_index, checked_state):
        """
        This method is used internally to check/uncheck all children of
        a given entity (eg to enable all shapes of a given layer when
        the user has enabled a layer)
        options
        @param item_model: the treeView model (used to store the data, see QT docs)
        @param item_index: the initial model index (QModelIndex) in the tree (all children of this index are scanned)
        @param checked_state: the state of the checkbox
        """

        for i in range(item_model.rowCount(item_index)):
            sub_item_index = item_model.index(i, 0, item_index)

            if item_model.hasChildren(sub_item_index):
                self.traverseChildrenAndEnableDisable(item_model, sub_item_index, checked_state)

            item = item_model.itemFromIndex(sub_item_index)
            if item and item.isEnabled():  # FIXME when parent was partially checked and a child cannot be checked
                self.updateCheckboxOfItem(item, checked_state)

    def traverseParentsAndUpdateEnableDisable(self, item_model, item_index):
        """
        This code updates the parents checkboxes for a given entity.
        Parents checkboxes are tristate, eg if some of the shapes that
        belong to a layer are checked and others not, then the checkbox
        of this layer will be "half" checked
        options
        @param item_model: the treeView model (used to store the data, see QT docs)
        @param item_index: the initial model index (QModelIndex) in the tree (all children of this index are scanned)
        """
        has_unchecked = False
        has_partially_checked = False
        has_checked = False
        item = None
        parent_item_index = None

        for i in range(item_model.rowCount(item_index.parent())):
            parent_item_index = item_model.index(i, 0, item_index.parent())

            item = item_model.itemFromIndex(parent_item_index)
            if item:
                if item.checkState() == QtCore.Qt.Checked:
                    has_checked = True
                elif item.checkState() == QtCore.Qt.PartiallyChecked:
                    has_partially_checked = True
                else:
                    has_unchecked = True

        # Update the parent item according to its children
        if item and item.parent():
            parent_state = item.parent().checkState()
            if has_checked and has_unchecked or has_partially_checked:
                parent_state = QtCore.Qt.PartiallyChecked
            elif has_checked and not has_unchecked:
                parent_state = QtCore.Qt.Checked
            elif not has_checked and has_unchecked:
                parent_state = QtCore.Qt.Unchecked

            self.updateCheckboxOfItem(item.parent(), parent_state)

            # Handle the parent of the parent (recursive call)
            if isValid(parent_item_index.parent()):
                self.traverseParentsAndUpdateEnableDisable(item_model, parent_item_index.parent())

    def toolUpdate(self):
        """
        Slot that updates the tool's diameter, speed and start_radius
        when a new tool is selected
        @param text: the name of the newly selected tool
        """
        text = self.ui.toolDiameterComboBox.currentText()
        if text:
            new_diameter = g.config.vars.Tool_Parameters[str(text)]['diameter']
            new_speed = g.config.vars.Tool_Parameters[str(text)]['speed']
            new_start_radius = g.config.vars.Tool_Parameters[str(text)]['start_radius']

            self.ui.toolDiameterComboBox.setPalette(self.palette)
            self.ui.toolDiameterLabel.setText(str(round(new_diameter, 3)))
            self.ui.toolDiameterLabel.setPalette(self.palette)  # Restore color
            self.ui.toolSpeedLabel.setText(str(round(new_speed, 1)))
            self.ui.toolSpeedLabel.setPalette(self.palette)  # Restore color
            self.ui.startRadiusLabel.setText(str(round(new_start_radius, 3)))
            self.ui.startRadiusLabel.setPalette(self.palette)  # Restore color

            # Get the new value and convert it to int
            val = toInt(text)
            if val[1]:
                selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

                for model_index in selected_indexes_list:
                    if isValid(model_index):
                        model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                        element = model_index.model().itemFromIndex(model_index)
                        real_item = None
                        if isValid(element.data(SHAPE_OBJECT)):
                            real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj.parentLayer  # Shape has no such property => update the parent layer
                        elif isValid(element.data(LAYER_OBJECT)):
                            real_item = toPyObject(element.data(LAYER_OBJECT))
                        if real_item is not None:
                            if real_item.tool_nr != val[0]:
                                real_item.tool_nr = val[0]
                                real_item.tool_diameter = new_diameter
                                real_item.speed = new_speed
                                real_item.start_radius = new_start_radius
                                self.tool_nr = real_item.tool_nr
                                self.tool_diameter = new_diameter
                                self.speed = new_speed
                                self.start_radius = new_start_radius
                                for shape in real_item.shapes:
                                    if isinstance(shape, Shape):
                                        # Only repaint _real_ shapes (and not the custom GCode for example)
                                        g.window.canvas_scene.repaint_shape(shape)
                if g.window and g.window.canvas_scene:
                    g.window.canvas_scene.update()

    def toolParameterzRetractionArealUpdate(self):
        """
        Slot that updates the above tools parameter when the
        corresponding LineEdit changes
        @param text: the value of the LineEdit
        """
        self.ui.zRetractionArealLineEdit.setPalette(self.palette)  # Restore color

        # Get the new value and convert it to float
        val = toFloat(self.ui.zRetractionArealLineEdit.text())
        if val[1]:
            selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

            for model_index in selected_indexes_list:
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    real_item = None
                    if isValid(element.data(SHAPE_OBJECT)):
                        real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj.parentLayer  # Shape has no such property => update the parent layer
                    elif isValid(element.data(LAYER_OBJECT)):
                        real_item = toPyObject(element.data(LAYER_OBJECT))
                    if real_item is not None:
                        real_item.axis3_retract = val[0]
                        self.axis3_retract = real_item.axis3_retract

    def toolParameterzSafetyMarginUpdate(self):
        """
        Slot that updates the above tools parameter when the
        corresponding LineEdit changes
        @param text: the value of the LineEdit
        """
        self.ui.zSafetyMarginLineEdit.setPalette(self.palette)  # Restore color

        # Get the new value and convert it to float
        val = toFloat(self.ui.zSafetyMarginLineEdit.text())
        if val[1]:
            selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

            for model_index in selected_indexes_list:
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    real_item = None
                    if isValid(element.data(SHAPE_OBJECT)):
                        real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj.parentLayer
                    elif isValid(element.data(LAYER_OBJECT)):
                        real_item = toPyObject(element.data(LAYER_OBJECT))
                    if real_item is not None:
                        real_item.axis3_safe_margin = val[0]
                        self.axis3_safe_margin = real_item.axis3_safe_margin

    def toolParameterzInfeedDepthUpdate(self):
        """
        Slot that updates the above tools parameter when the
        corresponding LineEdit changes
        @param text: the value of the LineEdit
        """
        self.ui.zInfeedDepthLineEdit.setPalette(self.palette)  # Restore color

        # Get the new value and convert it to float
        val = toFloat(self.ui.zInfeedDepthLineEdit.text())
        if val[1]:
            selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

            for model_index in selected_indexes_list:
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    if isValid(element.data(SHAPE_OBJECT)):
                        real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj
                        if real_item.axis3_slice_depth != val[0]:
                            real_item.axis3_slice_depth = val[0]
                            self.axis3_slice_depth = real_item.axis3_slice_depth
                            g.window.canvas_scene.repaint_shape(real_item)
            self.prepareExportOrderUpdate()
            g.window.canvas_scene.update()

    def toolParameterg1FeedXYUpdate(self):
        """
        Slot that updates the above tools parameter when the
        corresponding LineEdit changes
        @param text: the value of the LineEdit
        """
        self.ui.g1FeedXYLineEdit.setPalette(self.palette)  # Restore color

        # Get the new value and convert it to float
        val = toFloat(self.ui.g1FeedXYLineEdit.text())
        if val[1]:
            selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

            for model_index in selected_indexes_list:
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    if isValid(element.data(SHAPE_OBJECT)):
                        real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj
                        real_item.f_g1_plane = val[0]
                        self.f_g1_plane = real_item.f_g1_plane

    def toolParameterg1FeedZUpdate(self):
        """
        Slot that updates the above tools parameter when the
        corresponding LineEdit changes
        @param text: the value of the LineEdit
        """
        self.ui.g1FeedZLineEdit.setPalette(self.palette)  # Restore color

        # Get the new value and convert it to float
        val = toFloat(self.ui.g1FeedZLineEdit.text())
        if val[1]:
            selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

            for model_index in selected_indexes_list:
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    if isValid(element.data(SHAPE_OBJECT)):
                        real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj
                        real_item.f_g1_depth = val[0]
                        self.f_g1_depth = real_item.f_g1_depth

    def toolParameterzInitialMillDepthUpdate(self):
        """
        Slot that updates the above tools parameter when the
        corresponding LineEdit changes
        @param text: the value of the LineEdit
        """
        self.ui.zInitialMillDepthLineEdit.setPalette(self.palette)  # Restore color

        # Get the new value and convert it to float
        val = toFloat(self.ui.zInitialMillDepthLineEdit.text())
        if val[1]:
            selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

            for model_index in selected_indexes_list:
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    if isValid(element.data(SHAPE_OBJECT)):
                        real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj
                        if real_item.axis3_start_mill_depth != val[0]:
                            real_item.axis3_start_mill_depth = val[0]
                            self.axis3_start_mill_depth = real_item.axis3_start_mill_depth
                            g.window.canvas_scene.repaint_shape(real_item)
            self.prepareExportOrderUpdate()
            g.window.canvas_scene.update()

    def toolParameterzFinalMillDepthUpdate(self):
        """
        Slot that updates the above tools parameter when the
        corresponding LineEdit changes
        @param text: the value of the LineEdit
        """
        self.ui.zFinalMillDepthLineEdit.setPalette(self.palette)  # Restore color

        # Get the new value and convert it to float
        val = toFloat(self.ui.zFinalMillDepthLineEdit.text())
        if val[1]:
            selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

            for model_index in selected_indexes_list:
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    if isValid(element.data(SHAPE_OBJECT)):
                        real_item = toPyObject(element.data(SHAPE_OBJECT)).shapeobj
                        if real_item.axis3_mill_depth != val[0]:
                            real_item.axis3_mill_depth = val[0]
                            self.axis3_mill_depth = real_item.axis3_mill_depth
                            g.window.canvas_scene.repaint_shape(real_item)
            self.prepareExportOrderUpdate()
            g.window.canvas_scene.update()
            
    def actionOnSelectionChange(self, parent, selected, deselected):
        """
        This function is a callback called from QTreeView class when
        something changed in the selection. It aims to update the
        graphic view according to the tree selection. It also deals
        with children selection when a parent is selected
        Note that there is no predefined signal for
        selectionChange event, that's why we use a callback function
        options
        @param parent: QT parent item (unused)
        @param select: list of selected items in the treeView
        @param deselect: list of deselected items in the treeView
        """
        if not self.ui.layersShapesTreeView.selectionModel():
            return

        # if invoked from updateSelection() do nothing
        if hasattr (self, "updateSelectionInProgress"):
            return

        self.clearToolsParameters()  # disable tools parameters widgets, ...

        # Deselects all the shapes that are selected
        for selection in deselected:
            for model_index in selection.indexes():
                if isValid(model_index):
                    element = model_index.model().itemFromIndex(model_index)
                    if element:
                        if isValid(element.data(SHAPE_OBJECT)):
                            # Deselect the shape on the canvas
                            toPyObject(element.data(SHAPE_OBJECT)).shapeobj.setSelected(False)

                        elif isValid(element.data(CUSTOM_GCODE_OBJECT)):
                            toPyObject(element.data(CUSTOM_GCODE_OBJECT)).setSelected(False)

                        elif isValid(element.data(LAYER_OBJECT)):
                            self.traverseChildrenAndSelect(self.layer_item_model, model_index, False)

                        elif isValid(element.data(ENTITY_OBJECT)):
                            self.traverseChildrenAndSelect(self.entity_item_model, model_index, False)

        # Selects all the shapes that are selected
        lastSelected = None
        for selection in selected:
            for model_index in selection.indexes():
                if isValid(model_index):
                    model_index = model_index.sibling(model_index.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
                    element = model_index.model().itemFromIndex(model_index)
                    if element:
                        if isValid(element.data(SHAPE_OBJECT)):
                            lastSelected = toPyObject(element.data(SHAPE_OBJECT)).shapeobj
                            lastSelected.setSelected(True)  # Select the shape on the canvas

                        elif isValid(element.data(CUSTOM_GCODE_OBJECT)):
                            lastSelected = toPyObject(element.data(CUSTOM_GCODE_OBJECT))
                            lastSelected.setSelected(True)  # Select the shape on the canvas

                        # select all the children of a given layer when clicked
                        elif isValid(element.data(LAYER_OBJECT)):
                            self.traverseChildrenAndSelect(self.layer_item_model, model_index, True)
                            lastSelected = toPyObject(element.data(LAYER_OBJECT))

                        # select all the children of a given entity when clicked
                        elif isValid(element.data(ENTITY_OBJECT)):
                            self.traverseChildrenAndSelect(self.entity_item_model, model_index, True)

        # Update tree selection for both layer and entity pages
        self.updateSelection(self.ui.layersShapesTreeView)
        self.updateSelection(self.ui.entitiesTreeView)

        if lastSelected is not None:
            # update the tools parameters according to the selection
            parentLayer = getattr (lastSelected, 'parentLayer', None) or lastSelected
            self.displayToolParametersForItem(parentLayer, lastSelected)

        if g.window.canvas_scene:
            g.window.canvas_scene.update()

    def updateSelection(self, treeview):
        """
        Update selection of all tree items in a tree view according to value of
        .selected field of the object that corresponds to this tree item.

        This is called after massive item selections/deselections.
        """

        model = treeview.model()
        item_sel = QItemSelection()
        item_desel = QItemSelection()

        for branch in range(model.rowCount()):
            self.updateSelectionRecursive(model, model.index(branch, 0), item_sel, item_desel)

        # Block actionOnSelectionChange to avoid unselecting whole blocks
        # (because they are part of item_desel).
        self.updateSelectionInProgress = True
        selection = treeview.selectionModel()
        selection.select(item_sel, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        selection.select(item_desel, QItemSelectionModel.Deselect | QItemSelectionModel.Rows)

        del self.updateSelectionInProgress

    def updateSelectionRecursive(self, model, root, item_sel, item_desel):
        """
        Helper routine for updateSelection() used for recursion
        """
        if model.hasChildren(root):
            # always unselect layer and entity rows, otherwise selection misbehaves
            item_desel.select(root, root)
            for branch in range(model.rowCount(root)):
                self.updateSelectionRecursive(model, model.index(branch, 0, root), item_sel, item_desel)
        else:
            if isValid(root.data(SHAPE_OBJECT)):
                if toPyObject(root.data(SHAPE_OBJECT)).shapeobj.isSelected():
                    item_sel.select(root, root)
                else:
                    item_desel.select(root, root)
            elif isValid(root.data(CUSTOM_GCODE_OBJECT)):
                if toPyObject(root.data(CUSTOM_GCODE_OBJECT)).isSelected():
                    item_sel.select(root, root)
                else:
                    item_desel.select(root, root)

    def clearToolsParameters(self):
        """
        This function restore defaults for tools parameters widgets
        (disabled, default color, ...)
        """
        number_of_selected_items = len(self.ui.layersShapesTreeView.selectedIndexes())

        if number_of_selected_items <= 2:  # 2 selections = 1 row of 2 columns
            # 0 or 1 row are selected => clear some states
            self.tool_nr = None
            self.tool_diameter = None
            self.speed = None
            self.start_radius = None
            self.axis3_retract = None
            self.axis3_safe_margin = None
            self.axis3_slice_depth = None
            self.axis3_start_mill_depth = None
            self.axis3_mill_depth = None
            self.f_g1_plane = None
            self.f_g1_depth = None

            self.ui.toolDiameterComboBox.setPalette(self.palette)
            self.ui.toolDiameterLabel.setPalette(self.palette)
            self.ui.toolSpeedLabel.setPalette(self.palette)
            self.ui.startRadiusLabel.setPalette(self.palette)
            self.ui.zRetractionArealLineEdit.setPalette(self.palette)
            self.ui.zSafetyMarginLineEdit.setPalette(self.palette)
            self.ui.zInfeedDepthLineEdit.setPalette(self.palette)
            self.ui.g1FeedXYLineEdit.setPalette(self.palette)
            self.ui.g1FeedZLineEdit.setPalette(self.palette)
            self.ui.zInitialMillDepthLineEdit.setPalette(self.palette)
            self.ui.zFinalMillDepthLineEdit.setPalette(self.palette)

        if number_of_selected_items == 0:
            self.ui.millSettingsFrame.setEnabled(False)

        else:
            self.ui.millSettingsFrame.setEnabled(True)

    def updateToolParameters(self):
        """
        Refresh tool parameters for currently selected shape/layer.
        """
        if self.display_tool_layer is not None:
            self.displayToolParametersForItem(self.display_tool_layer, self.display_tool_shape)

    def displayToolParametersForItem(self, layer_item, shape_item = None):
        """
        Display the current tools settings (fill the QLineEdit, ...)
        for the Layer / Shape passed as parameter
        @param layer_item: layer instance as defined in LayerContent.py
        @param shape_item: shape instance as defined in Shape.py
        """

        self.display_tool_layer = layer_item
        self.display_tool_shape = shape_item

        # Selects the tool for the selected layer
        self.ui.toolDiameterComboBox.setCurrentIndex(self.ui.toolDiameterComboBox.findText(str(layer_item.tool_nr)))
        if self.tool_nr is not None and layer_item.tool_nr != self.tool_nr:
            # Several different tools are currently selected => grey background for the combobox
            palette = QPalette()
            palette.setColor(QPalette.Button, QtCore.Qt.gray)
            self.ui.toolDiameterComboBox.setPalette(palette)

        # Layer options
        self.tool_nr = layer_item.tool_nr

        self.tool_diameter = self.updateAndColorizeWidget(self.ui.toolDiameterLabel,
                                                          self.tool_diameter,
                                                          layer_item.tool_diameter)

        self.speed = self.updateAndColorizeWidget(self.ui.toolSpeedLabel,
                                                  self.speed, layer_item.speed)

        self.start_radius = self.updateAndColorizeWidget(self.ui.startRadiusLabel,
                                                         self.start_radius,
                                                         layer_item.start_radius)

        self.axis3_retract = self.updateAndColorizeWidget(self.ui.zRetractionArealLineEdit,
                                                          self.axis3_retract,
                                                          layer_item.axis3_retract)

        self.axis3_safe_margin = self.updateAndColorizeWidget(self.ui.zSafetyMarginLineEdit,
                                                              self.axis3_safe_margin,
                                                              layer_item.axis3_safe_margin)

        # Shape options
        if isinstance(shape_item, Shape): # To avoid segfault when someone passes eg Custom GCode as a shape_item
            self.axis3_start_mill_depth = self.updateAndColorizeWidget(self.ui.zInitialMillDepthLineEdit,
                                                                       self.axis3_start_mill_depth,
                                                                       shape_item.axis3_start_mill_depth)

            self.axis3_slice_depth = self.updateAndColorizeWidget(self.ui.zInfeedDepthLineEdit,
                                                                  self.axis3_slice_depth,
                                                                  shape_item.axis3_slice_depth)

            self.axis3_mill_depth = self.updateAndColorizeWidget(self.ui.zFinalMillDepthLineEdit,
                                                                 self.axis3_mill_depth,
                                                                 shape_item.axis3_mill_depth)
            
            if(False): #shape_item.Drill == True #drill removed
                self.ui.g1FeedXYLineEdit.setEnabled(False)
                self.f_g1_plane = self.updateAndColorizeWidget(self.ui.g1FeedXYLineEdit,
                                                           self.f_g1_plane,
                                                           shape_item.f_g1_plane)
            else:
                self.ui.g1FeedXYLineEdit.setEnabled(True)
                self.f_g1_plane = self.updateAndColorizeWidget(self.ui.g1FeedXYLineEdit,
                                                           self.f_g1_plane,
                                                           shape_item.f_g1_plane)
            

            self.f_g1_depth = self.updateAndColorizeWidget(self.ui.g1FeedZLineEdit,
                                                           self.f_g1_depth,
                                                           shape_item.f_g1_depth)

            #self.ui.OffsetXYLineEdit.setEnabled(shape_item.Pocket)
            #self.OffsetXY = self.updateAndColorizeWidget(self.ui.OffsetXYLineEdit,
            #                                               self.OffsetXY,
            #                                               shape_item.OffsetXY)
                
        else:
            for widget in self.ui.zInitialMillDepthLineEdit,\
                          self.ui.zInfeedDepthLineEdit,\
                          self.ui.zFinalMillDepthLineEdit,\
                          self.ui.g1FeedXYLineEdit,\
                          self.ui.g1FeedZLineEdit:
                widget.setText("")
                widget.setEnabled(False)
                
    def updatePocketMill(self, shape_item, enable):
        """
        This method is a "slot" (callback) called from the main when the
        Pocket Mill is enabled or disabled on the graphic view.
        It aims to update the Mill Settings Frame according to the
        graphic view.
        
        @param enable: whether the Shape has been enabled (True) or disabled (False)
        """
        
        """if(enable):
            self.ui.OffsetXYLineEdit.setEnabled(True)
            self.OffsetXY = self.updateAndColorizeWidget(self.ui.OffsetXYLineEdit,
                                                       self.OffsetXY,
                                                       shape_item.OffsetXY)
        else:
            self.ui.OffsetXYLineEdit.setEnabled(False)
            self.OffsetXY = self.updateAndColorizeWidget(self.ui.OffsetXYLineEdit,
                                                       self.OffsetXY,
                                                       shape_item.OffsetXY)
        """
        
    def updateDrill(self, shape_item, enable):
        """
        This method is a "slot" (callback) called from the main when the
        Drill is enabled or disabled on the graphic view.
        It aims to update the Mill Settings Frame according to the
        graphic view.
        
        @param enable: whether the Shape has been enabled (True) or disabled (False)
        """
        
        """
        if(enable):
            self.ui.OffsetXYLineEdit.setEnabled(False)
            self.ui.g1FeedXYLineEdit.setEnabled(False)
            #self.OffsetXY = self.updateAndColorizeWidget(self.ui.OffsetXYLineEdit,
            #                                           self.OffsetXY,
            #                                           shape_item.OffsetXY)
        else:
            self.ui.g1FeedXYLineEdit.setEnabled(True)
            #self.OffsetXY = self.updateAndColorizeWidget(self.ui.OffsetXYLineEdit,
            #                                           self.OffsetXY,
            #                                           shape_item.OffsetXY)
        """

    def updateAndColorizeWidget(self, widget, previous_value, value):
        """
        This function colours the text in grey when two values are
        different. It is used to show differences in tools settings
        when several layers / shapes are selected.
        @param widget: QT widget to update (can be a QLabel or a QLineEdit)
        @param previous_value: the value of the previously selected item
        @param value: the value (parameter) of the selected item
        """
        widget.setText(str(round(value, 4)))  # Round the value with at most 4 digits

        if previous_value and value != previous_value:
            # Several different tools parameter are currently selected (eg: mill deph = -3 for the first selected item and -2 for the second) => grey color for the text
            palette = QPalette()
            palette.setColor(QPalette.Text, QtCore.Qt.gray)
            widget.setPalette(palette)

        widget.setEnabled(True)

        return value

    def disableSelectedItems(self):
        selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

        for model_index in selected_indexes_list:
            if isValid(model_index):
                model_index = model_index.sibling(model_index.row(), 0)
                element = model_index.model().itemFromIndex(model_index)
                if element.isEnabled():
                    element.setCheckState(QtCore.Qt.Unchecked)

    def enableSelectedItems(self):
        selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

        for model_index in selected_indexes_list:
            if isValid(model_index):
                model_index = model_index.sibling(model_index.row(), 0)
                element = model_index.model().itemFromIndex(model_index)
                if element.isEnabled():
                    element.setCheckState(QtCore.Qt.Checked)

    def doNotOptimizeRouteForSelectedItems(self):
        selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

        for model_index in selected_indexes_list:
            if isValid(model_index):
                model_index = model_index.sibling(model_index.row(), PATH_OPTIMISATION_COL)
                element = model_index.model().itemFromIndex(model_index)
                if element.isEnabled():
                    element.setCheckState(QtCore.Qt.Unchecked)

    def optimizeRouteForSelectedItems(self):
        selected_indexes_list = self.ui.layersShapesTreeView.selectedIndexes()

        for model_index in selected_indexes_list:
            if isValid(model_index):
                model_index = model_index.sibling(model_index.row(), PATH_OPTIMISATION_COL)
                element = model_index.model().itemFromIndex(model_index)
                if element.isEnabled():
                    element.setCheckState(QtCore.Qt.Checked)

    def actionOnKeyPress(self, event):
        """
        This function is a callback called from QTreeView class when a
        key is pressed on the treeView. If the key is the spacebar, and O, then
        capture it to enable/disable shape and optimize path ...
        @param key_code: the key code as defined by QT
        @param item_index: the item on which the keyPress event occurred
        """

        # Enable/disable checkbox
        if event.key() == QtCore.Qt.Key_Space:
            for layer in self.layers_list:
                for shape in layer.shapes:
                    if shape.isSelected():
                        sub_item_index = self.findLayerItemIndexFromShape(shape)
                        # Get the first column of the row (ie the one that contains the enable/disable checkbox)
                        sub_item_index = sub_item_index.sibling(sub_item_index.row(), 0)
                        sub_item = sub_item_index.model().itemFromIndex(sub_item_index)
                        if sub_item.isEnabled():
                            # Toggle checkbox
                            sub_item.setCheckState(QtCore.Qt.Unchecked if sub_item.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked)

        # Optimize path checkbox
        elif event.key() == QtCore.Qt.Key_O:
            for layer in self.layers_list:
                for shape in layer.shapes:
                    if shape.isSelected():
                        sub_item_index = self.findLayerItemIndexFromShape(shape)
                        # Get the column of the row that contains the "Optimize Path" checkbox
                        sub_item_index = sub_item_index.sibling(sub_item_index.row(), PATH_OPTIMISATION_COL)
                        sub_item = sub_item_index.model().itemFromIndex(sub_item_index)
                        if sub_item.isEnabled():
                            # Toggle checkbox
                            sub_item.setCheckState(QtCore.Qt.Unchecked if sub_item.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked)
        else:
            return False
        return True

    def on_itemChanged(self, item):
        """
        This slot is called when some data changes in one of the
        TreeView. For us, since rows are read only, it is only
        triggered when a checkbox is checked/unchecked
        options
        @param item: item is the modified element. It can be a Shape, a Layer or an Entity
        """
        if item.column() == PATH_OPTIMISATION_COL:
            # User has clicked on the Path Optimisation (TSP) checkbox => update the corresponding data into the shape
            item_model_index = item.index().sibling(item.row(), 0)  # get the first column of the selected row, since it's the only one that contains data
            first_col_item = item_model_index.model().itemFromIndex(item_model_index)
            if isValid(first_col_item.data(SHAPE_OBJECT)):
                # Set tool path optimisation for the matching shape
                toPyObject(first_col_item.data(SHAPE_OBJECT)).shapeobj.setToolPathOptimized(False if item.checkState() == QtCore.Qt.Unchecked else True)

        elif isValid(item.data(SHAPE_OBJECT)) or isValid(item.data(CUSTOM_GCODE_OBJECT)):
            self.updateCheckboxOfItem(item, item.checkState())
            if self.auto_update_export_order:
                # update export order and thus export drawing
                self.prepareExportOrderUpdate()

        elif isValid(item.data(LAYER_OBJECT)):
            # Checkbox concerns a Layer object => check/uncheck each sub-items (shapes)
            self.traverseChildrenAndEnableDisable(self.layer_item_model, item.index(), item.checkState())
            if self.auto_update_export_order:
                self.prepareExportOrderUpdate()

        elif isValid(item.data(ENTITY_OBJECT)):
            # Checkbox concerns an Entity object => check/uncheck each sub-items (shapes and/or other entities)
            self.traverseChildrenAndEnableDisable(self.entity_item_model, item.index(), item.checkState())
            if self.auto_update_export_order:
                self.prepareExportOrderUpdate()

        g.window.canvas_scene.update()

    def updateCheckboxOfItem(self, item, check):
        """
        This function is used to effectively update the state of a
        checkbox and enable / disable texts when item is a shape
        @param item: item is the modified element. It can be a Shape, a Layer or an Entity
        @param check: the check state
        """
        item.model().blockSignals(True)  # Avoid unnecessary signal loops (we don't want the treeView to emit itemChanged signal)
        item.setCheckState(check)
        item.model().blockSignals(False)

        if isValid(item.data(SHAPE_OBJECT)):
            # Checkbox concerns a shape object
            real_item = toPyObject(item.data(SHAPE_OBJECT)).shapeobj
            real_item.setDisable(not check == QtCore.Qt.Checked)

            # Update the other TreeViews
            item_index = self.findEntityItemIndexFromShape(real_item)
            if item_index:
                if item.model() == self.layer_item_model:
                    self.entity_item_model.blockSignals(True)  # Avoid unnecessary signal loops (we don't want the treeView to emit itemChanged signal)
                    item_other_tree = self.entity_item_model.itemFromIndex(item_index)
                    item_other_tree.setCheckState(check)
                    self.enableDisableTreeRow(item_other_tree, check)
                    self.entity_item_model.blockSignals(False)
                self.traverseParentsAndUpdateEnableDisable(self.entity_item_model, item_index)  # Update parents checkboxes

            item_index = self.findLayerItemIndexFromShape(real_item)
            if item_index:
                if item.model() == self.entity_item_model:
                    self.layer_item_model.blockSignals(True)  # Avoid unnecessary signal loops (we don't want the treeView to emit itemChanged signal)
                    item_other_tree = self.layer_item_model.itemFromIndex(item_index)
                    item_other_tree.setCheckState(check)
                    self.enableDisableTreeRow(item_other_tree, check)
                    self.layer_item_model.blockSignals(False)
                self.traverseParentsAndUpdateEnableDisable(self.layer_item_model, item_index)  # Update parents checkboxes

        if isValid(item.data(CUSTOM_GCODE_OBJECT)):
            # Checkbox concerns a custom gcode object
            real_item = toPyObject(item.data(CUSTOM_GCODE_OBJECT))
            real_item.setDisable(not check == QtCore.Qt.Checked)
            self.traverseParentsAndUpdateEnableDisable(self.layer_item_model, item.index())  # Update parents checkboxes

        self.enableDisableTreeRow(item, check)

    def enableDisableTreeRow(self, item, check):
        """
        Enable / disable all the columns from a row, except the first
        one (because the first column contains the checkbox that must
        stay enabled in order to be clickable)
        @param item: item is the modified element.
                     It can be a Shape, a Layer or an Entity
        """
        if item.model() == self.layer_item_model:
            current_tree_view = self.ui.layersShapesTreeView
        else:
            current_tree_view = self.ui.entitiesTreeView

        item.model().blockSignals(True)
        if not item.parent():
            row_item = item.model().invisibleRootItem()  # parent is 0, so we need to get the root item of the tree as parent
            i = item.columnCount()
        else:
            row_item = item.parent()  # we are on one of the column of the row => take the parent, so that we get the complete row
            i = row_item.columnCount()
        row = item.row()
        while i > 1:
            i -= 1
            column_item = row_item.child(row, i)
            if column_item:
                column_item.setEnabled(False if check == QtCore.Qt.Unchecked else True)
                current_tree_view.update(column_item.index())
        item.model().blockSignals(False)

        # Update the display (refresh the treeView for the given item)
        current_tree_view.update(item.index())


    def removeCustomGCodeSelected(self):
        """
        Don't concat this function with removeCustomGCode()!
        (since the action that triggers "removeCustomGCode" sends a parameter, the "shape_item_index" is never set to None otherwise...)
        """
        self.removeCustomGCode(None)

    def removeCustomGCode(self, shape_item_index = None):
        """
        Remove a custom GCode object from the treeView, just after the
        current item. Custom GCode are defined into the config file
        """
        logger.debug('Removing custom GCode...')
        current_item_index = shape_item_index
        if current_item_index is None:
            # No parameter passed => we use current item
            current_item_index = self.ui.layersShapesTreeView.currentIndex()

        if isValid(current_item_index):
            remove_row = current_item_index.row()

            # get the first column of the selected row, since it's the only one that contains data
            item_model_index = current_item_index.sibling(remove_row, 0)
            first_col_item = item_model_index.model().itemFromIndex(item_model_index)
            if isValid(first_col_item.data(CUSTOM_GCODE_OBJECT)):
                # Item is a Custom GCode, so we can remove it
                real_item = toPyObject(first_col_item.data(CUSTOM_GCODE_OBJECT))
                real_item.parentLayer.shapes.remove(real_item)

                first_col_item.parent().removeRow(remove_row)

            else:
                logger.warning('Only Custom GCode items are removable!')

    def addCustomGCodeAfter(self, action_name):
        """
        Add a custom GCode object into the treeView, just after the
        current item. Custom GCode are defined into the config file
        @param action_name: the name of the custom GCode to be inserted.
                            This name must match one of the subsection names
                            of [Custom_Actions] from the config file.
        """
        logger.debug('Adding custom GCode "%s"' % action_name)

        g_code = "(No custom GCode defined)"
        if action_name and len(action_name) > 0:
            g_code = g.config.vars.Custom_Actions[str(action_name)].gcode

        current_item_index = self.ui.layersShapesTreeView.currentIndex()
        if isValid(current_item_index):
            push_row = current_item_index.row() + 1  # insert after the current row
            current_item = current_item_index.model().itemFromIndex(current_item_index)
            current_item_parent = current_item.parent()

            if not current_item_parent:
                # parent is 0, so we are probably on a layer
                # get the first column of the selected row, since it's the only one that contains data
                current_item_parent_index = current_item_index.sibling(current_item_index.row(), 0)
                current_item_parent = current_item_parent_index.model().itemFromIndex(current_item_parent_index)
                push_row = 0  # insert before any shape

            if isValid(current_item_parent.data(LAYER_OBJECT)):
                real_item_parent = toPyObject(current_item_parent.data(LAYER_OBJECT))

                # creates a new CustomGCode instance
                custom_gcode = CustomGCode(action_name, g.window.newNumber, g_code, real_item_parent)
                g.window.newNumber += 1

                # insert this new item at the end of the physical list
                real_item_parent.shapes.append(custom_gcode)

                self.AddCustomGCodeRowLayer(custom_gcode, current_item_parent, push_row)
                self.ui.layersShapesTreeView.setCurrentIndex(current_item.index())

    def prepareExportOrderUpdate(self):
        """
        If the live update of export route is enabled, this function is
        called each time the shape order changes. It aims to update the drawing.
        """
        if self.auto_update_export_order:
            # Update the exported shapes
            self.updateExportOrder()

            # Emit the signal "exportOrderUpdated", so that the main can update tool path if he wants
            g.window.updateExportRoute()

    def setLiveUpdateExportRoute(self, live_update):
        """
        Set or unset the live update of export route.
        """
        self.auto_update_export_order = live_update

        if self.auto_update_export_order:
            self.prepareExportOrderUpdate()
