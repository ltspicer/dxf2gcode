# dxf2gcode

2022-02-26 Release Candidate 1

Modifications inspired by https://sourceforge.net/p/dxf2gcode/sourcecode/ci/cbac98d2f079b0c39a5e9b86d5c320f36fa079b5/,
but no longer used.

This version generally works.
There are many things marked as TODO but it generates quite good g-code output.
This is RC1 version - it work's, but might be buggy.
```
dxf2gcode-pocketMill-RC1$ grep -Hrn '#TODO:' ./
./dxf2gcode/gui/canvas2d.py:41:                #TODO: check if can be removed:
./dxf2gcode/gui/canvas.py:31:                  #TODO: check if can be removed:
./dxf2gcode/core/pocketmill.py:56:             #TODO: remove everywhere: self.stmove.shape.OffsetXY
./dxf2gcode/core/pocketmill.py:364:            #TODO: check if shape like this:
./dxf2gcode/core/pocketmill.py:372:            #TODO: joints will propably cause problems
./dxf2gcode/core/pocketmill.py:481:            #TODO: beans shape:  (____)
./dxf2gcode/core/pocketmill.py:483:            #TODO: "Only lines and <180 angle.
./dxf2gcode/core/pocketmill.py:666:            #TODO: convert it to move based on horizontal and vertical lines only
./dxf2gcode/core/pocketmill.py:721:            #TODO: tweak?
./dxf2gcode/core/pocketmill.py:733:            #TODO: compensation type 41
./dxf2gcode/core/shape.py:244:                 #TODO: end point will change to zig-zag's end
./dxf2gcode/core/pocketmove.py:233:            #TODO: going Z-up can be done as full speed?
./dxf2gcode/globals/config.py:42:              #TODO: check if can be removed: from dns.rdataclass import NONE
```
TODO:
- convert blue lines (path) with tool-width path
- reenable pocket mill when machine compensation is done by machine

Please donate: https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=XS8G3MZ896XNQ&item_name=pocket+milling&currency_code=EUR&source=url
