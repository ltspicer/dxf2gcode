# -*- coding: utf-8 -*-

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

import logging
import hashlib
import re

from dxf2gcode.core.point import Point
from dxf2gcode.core.customgcode import CustomGCode
from dxf2gcode.core.layercontent import Layers, Shapes
from dxf2gcode.globals.d2gexceptions import VersionMismatchError
import dxf2gcode.globals.globals as g

import dxf2gcode.globals.constants as c
from PyQt5 import QtCore

logger = logging.getLogger("Core.Project")

def execute(self, content):
    # hack to use exec with local variables, for sure; To prevent the following error
    # SyntaxError: unqualified exec is not allowed in function 'load' it contains a nested function with free variables
    # this error is a Python 2.7 compiler bug (http://bugs.python.org/issue21591) - might occur in the earlier versions
    exec(content, {'d2g': self})

class Project(object):
    header = "# +~+~+~ DXF2GCODE project file V%s ~+~+~+"
    supported_versions = [1.1, 1.2, 1.3]
    version = supported_versions[-1]

    def __init__(self, parent):
        self.parent = parent

        self.file = None
        self.point_tol = None
        self.fitting_tol = None
        self.scale = None
        self.rot = None
        self.wpzero_x = None
        self.wpzero_y = None
        self.mirrorx = None
        self.mirrory = None
        self.split_lines = None
        self.aut_cut_com = None
        self.machine_type = None

        self.layers = None

    def tr(self, string_to_translate):
        """
        Translate a string using the QCoreApplication translation framework
        @param: string_to_translate: a unicode string
        @return: the translated unicode string if it was possible to translate
        """
        return str(QtCore.QCoreApplication.translate('Project',
                                                           string_to_translate))

    def get_hash(self, shape, version, compleet=True):
        reverse = False
        if not shape.cw:
            reverse = True
            shape.reverse()

        shape_iter = shape.geos if version < 1.2 else shape.geos.abs_iter()  # new versions look at absolute values
        geos = [geo.save_v1() for geo in shape_iter]
        if reverse:
            shape.reverse()
        if compleet:
            return hashlib.sha1(''.join(sorted(geos)).encode('utf-8')).hexdigest()
        #If it's not a compleet reload change the hash to something more identical. This might enable a reload with previous settings
        #For Rot / sca / wp move etc. hash will not be identical with above algorithm as they are changed. but the Shape.nr will stay the same.
        else:
            return hashlib.sha1(('%s' %(shape.nr)).encode('utf-8')).hexdigest()
        

    def export(self,compleet=True):
        self.parent.TreeHandler.updateExportOrder(True)
        layers = []
        for layer in self.parent.layerContents:
            shapes = []
            for nr in layer.exp_order_complete:
                shape = layer.shapes[nr]
                if isinstance(shape, CustomGCode):
                    shapes.append({'gcode': shape.gcode,
                                   'name': shape.name,
                                   'disabled': shape.disabled})
                else:
                    stpoint = shape.get_start_end_points(True)
                    shapes.append({'hash_': self.get_hash(shape, Project.version, compleet),
                                   'cut_cor': shape.cut_cor,
                                   'Pocket_Mill': shape.Pocket,
                                   'Drill': shape.Drill,
                                   'cw': shape.cw,
                                   'send_to_TSP': shape.send_to_TSP,
                                   'disabled': shape.disabled,
                                   'start_mill_depth': shape.axis3_start_mill_depth,
                                   'slice_depth': shape.axis3_slice_depth,
                                   'mill_depth': shape.axis3_mill_depth,
                                   'f_g1_plane': shape.f_g1_plane,
                                   'f_g1_depth': shape.f_g1_depth,
                                   'start_x': stpoint.x,
                                   'start_y': stpoint.y})
            layers.append({'name': layer.name,
                           'tool_nr': layer.tool_nr,
                           'diameter': layer.tool_diameter,
                           'speed': layer.speed,
                           'start_radius': layer.start_radius,
                           'retract': layer.axis3_retract,
                           'safe_margin': layer.axis3_safe_margin,
                           'shapes': shapes})

        pyCode = Project.header % str(Project.version) + '''
d2g.file = "''' + self.parent.filename + '''"
d2g.point_tol = ''' + str(g.config.point_tolerance) + '''
d2g.fitting_tol = ''' + str(g.config.fitting_tolerance) + '''
d2g.scale = ''' + str(self.parent.cont_scale) + '''
d2g.rot = ''' + str(self.parent.cont_rotate) + '''
d2g.wpzero_x = ''' + str(self.parent.cont_dx) + '''
d2g.wpzero_y = ''' + str(self.parent.cont_dy) + '''
d2g.mirrorx = ''' + str(self.parent.cont_mirrorx) + '''
d2g.mirrory = ''' + str(self.parent.cont_mirrory) + '''
d2g.split_lines = ''' + str(self.parent.ui.actionSplitLineSegments.isChecked()) + '''
d2g.aut_cut_com = ''' + str(self.parent.ui.actionAutomaticCutterCompensation.isChecked()) + '''
d2g.machine_type = "''' + g.config.machine_type + '''"
d2g.layers = ''' + str(layers)
        return pyCode

    def load(self, content, compleet=True):
        match = re.match(Project.header.replace('+', '\+') % r'(\d+\.\d+)', content)
        if not match:
            raise Exception('Incorrect project file')
        version = float(match.groups()[0])
        if version not in  Project.supported_versions:
            raise VersionMismatchError(match.group(), Project.version)

        execute(self, content)

        if compleet:
            self.parent.filename = self.file
            g.config.point_tolerance = self.point_tol
            g.config.fitting_tolerance = self.fitting_tol

        # If one of scale / move / rot variables has changed the reload will not identify the shape to be similar.
        # Therefore try to move those variables at the end and do a second reload afterwards.
            self.parent.cont_scale = self.scale
            self.parent.cont_rotate = self.rot
            self.parent.cont_dx = self.wpzero_x
            self.parent.cont_dy = self.wpzero_y

            #New Variable with version 1.3
            if version<1.3:
                self.parent.cont_mirrorx = False
                self.parent.cont_mirrory = False
            else:
                self.parent.cont_mirrorx = self.mirrorx
                self.parent.cont_mirrory = self.mirrory

            g.config.vars.General['split_line_segments'] = self.split_lines
            g.config.vars.General['automatic_cutter_compensation'] = self.aut_cut_com
            g.config.machine_type = self.machine_type

            self.parent.connectToolbarToConfig(True)
            if not self.parent.load(False):
                self.parent.unsetCursor()
                return

        name_layers = dict((layer.name, layer) for layer in self.parent.layerContents)
        # dict comprehensions are supported since Py2.7
        # name_layers = {layer.name: layer for layer in self.parent.layerContents}

        layers = []
        for parent_layer in self.layers:
            if parent_layer['name'] in name_layers:
                layer = name_layers[parent_layer['name']]
                layer.tool_nr = parent_layer['tool_nr']
                layer.tool_diameter = parent_layer['diameter']
                layer.speed = parent_layer['speed']
                layer.start_radius = parent_layer['start_radius']

                layer.axis3_retract = parent_layer['retract']
                layer.axis3_safe_margin = parent_layer['safe_margin']

                # hash_shapes = dict((self.get_hash(shape), shape) for shape in layer.shapes)
                # dict comprehensions are supported since Py2.7
                # hash_shapes = {self.get_hash(shape): shape for shape in layer.shapes}
                hash_shapes = dict()
                for shape in layer.shapes:
                    shape_hash = self.get_hash(shape, version, compleet)
                    if shape_hash in hash_shapes:
                        hash_shapes[shape_hash].insert(0, shape)
                    else:
                        hash_shapes[shape_hash] = [shape]

                

                shapes = []
                for parent_shape in parent_layer['shapes']:
                    if 'gcode' in parent_shape:
                        shape = CustomGCode(parent_shape['name'], self.parent.newNumber, parent_shape['gcode'], layer)
                        self.parent.newNumber += 1
                        shape.disabled = parent_shape['disabled']
                        shapes.append(shape)
                    elif parent_shape['hash_'] in hash_shapes:
                        shape_list = hash_shapes[parent_shape['hash_']]
                        shape = shape_list.pop()
                        if len(shape_list) == 0:
                            del hash_shapes[parent_shape['hash_']]
                        shape.cut_cor = parent_shape['cut_cor']
                        shape.Pocket = parent_shape['Pocket_Mill']
                        shape.Drill = parent_shape['Drill']
                        shape.send_to_TSP = parent_shape['send_to_TSP']
                        shape.disabled = parent_shape['disabled']
                        shape.axis3_start_mill_depth = parent_shape['start_mill_depth']
                        shape.axis3_slice_depth = parent_shape['slice_depth']
                        shape.axis3_mill_depth = parent_shape['mill_depth']
                        shape.f_g1_plane = parent_shape['f_g1_plane']
                        shape.f_g1_depth = parent_shape['f_g1_depth']
                        
                        if parent_shape['cw'] != shape.cw:
                            shape.reverse()
                        shape.setNearestStPoint(Point(parent_shape['start_x'], parent_shape['start_y']))
                        shapes.append(shape)
                new_shapes = set(layer.shapes) - set(shapes);
                shapes.extend(new_shapes)  # add "new" shapes to the end
                layer.shapes = Shapes(shapes)  # overwrite original
                if len(new_shapes) > 0:
                    logger.info(self.tr("New/Unrecognized shapes added for layer:%s; %s") %
                                (layer.name, [shape.nr for shape in new_shapes]))

                layers.append(layer)

        layers.extend(set(self.parent.layerContents) - set(layers))  # add "new" layers to the end
        self.parent.layerContents = Layers(layers)  # overwrite original
        self.parent.plot()

    def reload(self, compleet=True):
        if self.parent.filename:
            self.parent.setCursor(QtCore.Qt.WaitCursor)
            self.parent.canvas.resetAll()
            self.parent.app.processEvents()
            pyCode = self.export(compleet)
            self.parent.makeShapes()
            self.load(pyCode, compleet)

    def small_reload(self,):
        self.reload(False)
