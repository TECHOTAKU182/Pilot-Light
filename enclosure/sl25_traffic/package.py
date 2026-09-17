"""Verify exported files again, then package the source and printable parts."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.append(os.environ.get("FREECAD_LIB", r"E:\freecad\lib"))
import FreeCAD
import Mesh
import Part
from PIL import Image

root = Path(__file__).resolve().parent
workspace = root.parents[1]
validation = json.loads((root / "checks/validation.json").read_text())
assert validation["passed"], validation["failures"]
result = {"stl_reopen": {}, "step_reopen": {}, "preview_sizes": {}}
for path in sorted((root / "stl").glob("*.stl")):
    mesh = Mesh.Mesh(str(path))
    assert mesh.isSolid() and not mesh.hasNonManifolds(), path
    result["stl_reopen"][path.name] = "closed manifold mesh"
for path in sorted((root / "cad").glob("*.step")):
    shape = Part.read(str(path))
    assert shape.isValid() and len(shape.Solids) > 0, path
    result["step_reopen"][path.name] = {"valid": True, "solids": len(shape.Solids)}
with zipfile.ZipFile(root / "cad/SL25_Traffic_A.FCStd") as archive:
    gui = ET.fromstring(archive.read("GuiDocument.xml"))
    visible = [v.get("name") for v in gui.iter("ViewProvider")
               for p in v.findall("./Properties/Property")
               if p.get("name") == "Visibility" and p.find("Bool").get("value") == "true"]
    assert len(visible) == 7, visible
    result["fcstd_visible_objects"] = visible
for path in sorted((root / "preview").glob("*.png")):
    with Image.open(path) as image:
        result["preview_sizes"][path.name] = list(image.size)
        assert len(image.getcolors(image.width * image.height)) > 20, path
result["passed"] = True
(root / "checks/export_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

files = [p for p in root.rglob("*") if p.is_file()
         and p.suffix not in (".FCBak", ".pyc") and "__pycache__" not in p.parts
         and p.name != "SHA256SUMS.json"]
files += [workspace / "hardware/sl25/mechanical/sl25.step",
          workspace / "hardware/sl25/mechanical/interface.json"]
checksums = {p.relative_to(workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(files)}
checksum_path = root / "SHA256SUMS.json"
checksum_path.write_text(json.dumps(checksums, indent=2), encoding="utf-8")
files.append(checksum_path)
complete = root.parent / "SL25-Traffic-Enclosure-RevA.zip"
with zipfile.ZipFile(complete, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(files):
        archive.write(path, path.relative_to(workspace).as_posix())
with zipfile.ZipFile(complete) as archive:
    assert archive.testzip() is None
    for path, expected in checksums.items():
        assert hashlib.sha256(archive.read(path)).hexdigest() == expected
print("Source package:", complete, complete.stat().st_size, "bytes")

printable = root.parent / "SL25-Traffic-STL-RevA.zip"
with zipfile.ZipFile(printable, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted((root / "stl").glob("*.stl")):
        archive.write(path, path.name)
    archive.write(root / "README.md", "README.md")
    archive.write(root / "preview/dimensions.png", "dimensions.png")
with zipfile.ZipFile(printable) as archive:
    assert archive.testzip() is None
print("Print package:", printable, printable.stat().st_size, "bytes")
