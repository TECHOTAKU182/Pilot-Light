"""Reopen the coordinated Rev B exports and package CAD, PCB, and cut sheets."""
from pathlib import Path
import hashlib
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.append(os.environ.get("FREECAD_LIB", r"E:\freecad\lib"))
import FreeCAD
import Part
import Mesh
from PIL import Image

root = Path(__file__).resolve().parent
pcb = root / "hardware/sl25_rev_b"
case = root / "enclosure/sl25_traffic_rev_b"
assert json.loads((pcb / "checks/verification.json").read_text())["passed"]
validation = json.loads((case / "checks/validation.json").read_text())
assert validation["passed"], validation["failures"]
assert validation["enclosure_size_mm"] == [30, 30, 40]
assert validation["hood_profile"]["top_projection_mm"] == 15
assert validation["clearances_mm"]["required_LED_tip_to_diffuser"] >= 13.5
result = {"stl_reopen": {}, "step_reopen": {}, "svg_cut_contours": {}, "previews": {}}
for path in sorted((case / "stl").glob("*.stl")):
    mesh = Mesh.Mesh(str(path))
    assert mesh.isSolid() and not mesh.hasNonManifolds(), path
    assert abs(mesh.BoundBox.ZMin) < 1e-5
    result["stl_reopen"][path.name] = "closed manifold; bed at Z=0"
for path in sorted((case / "cad").glob("*.step")) + [pcb / "mechanical/sl25.step"]:
    shape = Part.read(str(path))
    assert shape.isValid() and len(shape.Solids), path
    result["step_reopen"][path.relative_to(root).as_posix()] = {"valid": True, "solids": len(shape.Solids)}
source = Part.read(str(pcb / "mechanical/sl25.step"))
led = [s for s in source.Solids if s.BoundBox.ZMin >= 1.55]
assert len(led) == 1
center = led[0].BoundBox.Center
assert abs(center.x - 12.5) < 1e-6 and abs(center.y + 12.5) < 1e-6
result["LED_STEP_center_mm"] = [center.x, center.y]
with zipfile.ZipFile(case / "cad/SL25_Traffic_B.FCStd") as archive:
    gui = ET.fromstring(archive.read("GuiDocument.xml"))
    visible = [v.get("name") for v in gui.iter("ViewProvider") for p in v.findall("./Properties/Property")
               if p.get("name") == "Visibility" and p.find("Bool").get("value") == "true"]
    assert len(visible) == 10, visible
    result["fcstd_visible_objects"] = len(visible)
for path in (case / "cut_templates").glob("0*.svg"):
    svg = ET.parse(path).getroot()
    diameters = [2 * float(c.get("r")) for c in svg.findall("{http://www.w3.org/2000/svg}circle")]
    assert diameters == ([26, 24] if "foam" in path.name else [26]), path
    assert svg.get("width") == "28mm"
    result["svg_cut_contours"][path.name] = diameters
for path in list((case / "preview").glob("*.png")) + list((pcb / "preview").glob("*.png")):
    with Image.open(path) as image:
        assert len(image.getcolors(image.width * image.height)) > 20, path
        result["previews"][path.relative_to(root).as_posix()] = list(image.size)
result["passed"] = True
(case / "checks/export_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

files = []
for folder in (pcb, case):
    files += [p for p in folder.rglob("*") if p.is_file()
              and p.suffix not in (".FCBak", ".pyc", ".kicad_prl", ".lck")
              and "__pycache__" not in p.parts and p.name != "SHA256SUMS.json"]
files += [root / "hardware" / name for name in
          ("generate_board.py", "generate_rev_b.py", "route_board.py", "route_rev_b.py", "finish_board.py", "verify_rev_b.py")]
files += [root / "hardware/reference" / name for name in ("CH552.pdf", "USB4105.pdf", "WS2812B-V5.pdf")]
files += [root / "CURRENT_DESIGN.md", root / "package_rev_b.py"]
hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
checksum = case / "SHA256SUMS.json"
checksum.write_text(json.dumps(hashes, indent=2), encoding="utf-8")
files.append(checksum)
complete = root / "SL25-RevB-complete.zip"
with zipfile.ZipFile(complete, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(files):
        archive.write(path, "SL25-RevB/" + path.relative_to(root).as_posix())
with zipfile.ZipFile(complete) as archive:
    assert archive.testzip() is None
    for name, expected in hashes.items():
        assert hashlib.sha256(archive.read("SL25-RevB/" + name)).hexdigest() == expected

gerbers = root / "hardware/SL25-RevB-gerbers.zip"
with zipfile.ZipFile(gerbers, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in (pcb / "fabrication").iterdir():
        if path.suffix in (".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo", ".gtp", ".gbp", ".gm1", ".drl", ".gbrjob"):
            archive.write(path, path.name)
printable = root / "enclosure/SL25-Traffic-STL-RevB.zip"
with zipfile.ZipFile(printable, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in (case / "stl").glob("*.stl"):
        archive.write(path, "stl/" + path.name)
    for path in (case / "cut_templates").glob("*.svg"):
        archive.write(path, "cut_templates/" + path.name)
    archive.write(case / "README.md", "README.md")
    archive.write(case / "preview/dimensions.png", "dimensions.png")
    archive.write(case / "preview/hood_profile.png", "hood_profile.png")
for path in (complete, gerbers, printable):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
    print(str(path), path.stat().st_size, "bytes")
print("All exported files reopened and validated.")
