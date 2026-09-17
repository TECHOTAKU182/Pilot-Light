"""Store object visibility and colors without opening a visible FreeCAD window."""
import json
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.append(os.environ.get("FREECAD_LIB", r"E:\freecad\lib"))
import FreeCAD as App
import FreeCADGui as Gui

root = Path(__file__).resolve().parent
manifest = json.loads((root / "cad/objects.json").read_text())
Gui.showMainWindow()
Gui.getMainWindow().hide()
doc = App.openDocument(str(root / "cad/SL25_Traffic_B.FCStd"))
for obj in doc.Objects:
    if obj.ViewObject:
        obj.ViewObject.Visibility = False
for name, info in {**manifest["parts"], **manifest["optics"]}.items():
    obj = doc.getObject(info["object"])
    obj.ViewObject.ShapeColor = tuple(info["color"])
    obj.ViewObject.LineColor = (0.12, 0.13, 0.14)
    obj.ViewObject.DisplayMode = "Flat Lines"
    obj.ViewObject.Visibility = True
    if name == "06_clear_protector":
        obj.ViewObject.Transparency = 85
for name in manifest["fasteners"]:
    obj = doc.getObject(name)
    obj.ViewObject.ShapeColor = (0.65, 0.68, 0.71)
    obj.ViewObject.Visibility = True
pcb = doc.getObject(manifest["reference"])
pcb.ViewObject.ShapeColor = (0.12, 0.45, 0.25)
pcb.ViewObject.Visibility = True
doc.recompute()
doc.save()
print("Saved CAD display properties.")
App.closeDocument(doc.Name)
Gui.getMainWindow().close()
