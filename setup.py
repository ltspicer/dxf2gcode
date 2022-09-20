#!/usr/bin/python3
# To create MSI installer with automatic Menu shortcut installation run the following:
# python3 setup.py bdist_msi

import os
import shutil
import sys

from cx_Freeze import Executable, setup


version = "20220226"

base = 'Console'
if sys.platform == 'win32':
    base = 'Win32GUI'  # Tells the build script to hide the console.


# script based on
# https://github.com/Fireforge/PySide-OpenGL-cx_Freeze-Example
# http://stackoverflow.com/questions/15486292/cx-freeze-doesnt-find-all-dependencies
def include_OpenGL():
    PYTHONPATH = os.path.split(sys.executable)[0]
    path_base = os.path.join(PYTHONPATH, "Lib\\site-packages\\OpenGL")
    skip_count = len(path_base)
    zip_includes = [(path_base, "OpenGL")]
    for root, sub_folders, files in os.walk(path_base):
        for file_in_root in files:
            zip_includes.append(
                ("{}".format(os.path.join(root, file_in_root)),
                 "{}".format(os.path.join("OpenGL", root[skip_count + 1:], file_in_root))
                 )
            )
    return zip_includes


# Remove the existing folders
shutil.rmtree("build", ignore_errors=True)
shutil.rmtree("dist", ignore_errors=True)



includefiles = ['COPYING',
                'README.txt',
                ('i18n\dxf2gcode_de.qm', 'i18n\dxf2gcode_de.qm'),
                ('i18n\dxf2gcode_fr.qm', 'i18n\dxf2gcode_fr.qm'),
                ('i18n\dxf2gcode_ru.qm', 'i18n\dxf2gcode_ru.qm')
                ]
includes = []
excludes = []



options = {
    'build_exe': {
        # 'packages': '' ,
        'includes':includes,
        'excludes':excludes,
        'include_files':includefiles,
        'zip_includes': include_OpenGL(),
        'silent': True
    }
}



executables = [
    Executable(script='dxf2gcode.py',
               base=base,
               icon="images\\DXF2GCODE-001.ico",
               target_name="dxf2gcode.exe",
               shortcut_name="DXF to G-Code Converter",
               shortcut_dir="ProgramMenuFolder"
               )
]

#If you want to run the script directly uncomment the following.
#sys.argv.append("bdist_msi")


setup(name='DXF2GCODE',
      version=version[0:4] + "." + version[4:6] + "." + version[6:8],  # converts YYYYMMDD -> YYYY.MM.DD
      description='Converting 2D drawings to CNC machine compatible G-Code. Release Candidate based on development branch',
      options=options,
      executables=executables
      )
