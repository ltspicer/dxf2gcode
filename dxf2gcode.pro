TARGET = dxf2gcode.py

SOURCES += \
    dxf2gcode.py \
    make_tr.py \
    dxf2gcode.py \
    make_exe.py \
    make_py_uic.py \
    make_tr.py \
    setup.py \
    st-setup.py \
    dxf2gcode/__init__.py \
    dxf2gcode/core/__init__.py \
    dxf2gcode/core/arcgeo.py \
    dxf2gcode/core/point.py \
    dxf2gcode/core/boundingbox.py \
    dxf2gcode/core/breakgeo.py \
    dxf2gcode/core/customgcode.py \
    dxf2gcode/core/entitycontent.py \
    dxf2gcode/core/holegeo.py \
    dxf2gcode/core/intersect.py \
    dxf2gcode/core/layercontent.py \
    dxf2gcode/core/linegeo.py \
    dxf2gcode/core/pocketmill.py \
    dxf2gcode/core/pocketmove.py \
    dxf2gcode/core/point3d.py \
    dxf2gcode/core/project.py \
    dxf2gcode/core/shape.py \
    dxf2gcode/core/shapeoffset.py \
    dxf2gcode/core/stmove.py \
    dxf2gcode/globals/__init__.py \
    dxf2gcode/globals/config.py \
    dxf2gcode/globals/constants.py \
    dxf2gcode/globals/d2gexceptions.py \
    dxf2gcode/globals/globals.py \
    dxf2gcode/globals/helperfunctions.py \
    dxf2gcode/globals/logger.py \
    dxf2gcode/gui/__init__.py \
    dxf2gcode/gui/aboutdialog.py \
    dxf2gcode/gui/arrow.py \
    dxf2gcode/gui/canvas.py \
    dxf2gcode/gui/canvas2d.py \
    dxf2gcode/gui/canvas3d.py \
    dxf2gcode/gui/configwindow.py \
    dxf2gcode/gui/messagebox.py \
    dxf2gcode/gui/popupdialog.py \
    dxf2gcode/gui/routetext.py \
    dxf2gcode/gui/treehandling.py \
    dxf2gcode/gui/treeview.py \
    dxf2gcode/gui/wpzero.py \
    dxf2gcode/dxfimport/__init__.py \
    dxf2gcode/dxfimport/biarc.py \
    dxf2gcode/dxfimport/classes.py \
    dxf2gcode/dxfimport/geoent_arc.py \
    dxf2gcode/dxfimport/geoent_circle.py \
    dxf2gcode/dxfimport/geoent_ellipse.py \
    dxf2gcode/dxfimport/geoent_insert.py \
    dxf2gcode/dxfimport/geoent_line.py \
    dxf2gcode/dxfimport/geoent_lwpolyline.py \
    dxf2gcode/dxfimport/geoent_point.py \
    dxf2gcode/dxfimport/geoent_polyline.py \
    dxf2gcode/dxfimport/geoent_spline.py \
    dxf2gcode/dxfimport/importer.py \
    dxf2gcode/dxfimport/spline_convert.py \
    dxf2gcode/postpro/__init__.py \
    dxf2gcode/postpro/breaks.py \
    dxf2gcode/postpro/postprocessor.py \
    dxf2gcode/postpro/postprocessorconfig.py \
    dxf2gcode/postpro/tspoptimisation.py

DISTFILES += \
    README.txt \
    dxf2gcode.desktop \
    dxf2gcode.appdata.xml \
    MANIFEST.in

RESOURCES += \
    dxf2gcode_images.qrc

FORMS += \
    dxf2gcode.ui

TRANSLATIONS += \
    i18n/dxf2gcode_de.ts \
    i18n/dxf2gcode_fr.ts \
    i18n/dxf2gcode_ru.ts
