"""Regenerate the enclosure using FreeCAD's Python interpreter.

Dimensions are in parameters.json. Native primitives and Boolean history remain
editable in FCStd; changing JSON requires rerunning this script.
"""
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys

sys.path.append(os.environ.get("FREECAD_LIB", r"E:\freecad\lib"))
import FreeCAD as App
import Part
import Mesh
import MeshPart

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / "parameters.json").read_text(encoding="utf-8"))
for directory in ("cad", "stl", "checks", "preview"):
    (ROOT / directory).mkdir(exist_ok=True)
DOC = App.newDocument("SL25_Traffic_A")
SERIAL = itertools.count(1)
ALL_FEATURES = []


def feature(kind, label):
    obj = DOC.addObject(kind, "F%03d" % next(SERIAL))
    obj.Label = label
    ALL_FEATURES.append(obj)
    return obj


def box(label, x, y, z, width, height, depth):
    obj = feature("Part::Box", label)
    obj.Length, obj.Width, obj.Height = width, height, depth
    obj.Placement.Base = App.Vector(x, y, z)
    DOC.recompute()
    return obj


def cylinder(label, x, y, z, radius, depth):
    obj = feature("Part::Cylinder", label)
    obj.Radius, obj.Height = radius, depth
    obj.Placement.Base = App.Vector(x, y, z)
    DOC.recompute()
    return obj


def cone(label, x, y, z, r1, r2, depth):
    obj = feature("Part::Cone", label)
    obj.Radius1, obj.Radius2, obj.Height = r1, r2, depth
    obj.Placement.Base = App.Vector(x, y, z)
    DOC.recompute()
    return obj


def fuse(label, objects):
    obj = feature("Part::MultiFuse", label)
    obj.Shapes = objects
    obj.Refine = True
    DOC.recompute()
    return obj


def cut(label, base, tool):
    obj = feature("Part::Cut", label)
    obj.Base, obj.Tool, obj.Refine = base, tool, True
    DOC.recompute()
    return obj


def common(label, base, tool):
    obj = feature("Part::Common", label)
    obj.Base, obj.Tool, obj.Refine = base, tool, True
    DOC.recompute()
    return obj


def rounded(label, x, y, z, width, height, depth, radius):
    shapes = [box(label + " web X", x + radius, y, z,
                  width - 2 * radius, height, depth),
              box(label + " web Y", x, y + radius, z,
                  width, height - 2 * radius, depth)]
    for cx in (x + radius, x + width - radius):
        for cy in (y + radius, y + height - radius):
            shapes.append(cylinder(label + " corner", cx, cy, z, radius, depth))
    return fuse(label, shapes)


def usb_tool():
    return box("USB plug overmold opening", (P["width"] - P["usb_opening_width"]) / 2,
               -1, P["usb_center_z"] - P["usb_opening_height"] / 2,
               P["usb_opening_width"], P["usb_cut_depth"] + 1,
               P["usb_opening_height"])


W, H, Z = P["width"], P["height"], P["depth"]
wall, floor, seam = P["wall"], P["rear_floor"], P["pcb_bottom_z"]
face, inner = P["face_z"], P["face_z"] - P["face_thickness"]
board_top = seam + P["pcb_thickness"]
mount_r = P["mount_boss_diameter"] / 2
cx, cy = P["lens_center"]

# Rear tray supports the PCB at its mounting holes. Screws pass through the
# existing holes into the front housing's pilot bores.
rear_blank = rounded("Rear tray outside", 0, 0, 0, W, H, seam, P["corner_radius"])
rear_cavity = rounded("Rear tray pocket", floor, floor, floor,
                     W - 2 * floor, H - 2 * floor, seam,
                     P["corner_radius"] - floor)
rear = cut("Rear tray walls", rear_blank, rear_cavity)
rear_register_pocket = rounded(
    "Rear register receiving step", P["rear_register_lip"], P["rear_register_lip"],
    seam - P["register_depth"], W - 2 * P["rear_register_lip"],
    H - 2 * P["rear_register_lip"], P["register_depth"] + 0.01,
    P["corner_radius"] - P["rear_register_lip"])
rear = cut("Rear registration rabbet", rear, rear_register_pocket)
rear_posts = [cylinder("PCB rear support", x, y, floor - 0.01,
                       mount_r, seam - floor + 0.01) for x, y in P["mounts"]]
rear = fuse("Rear tray with supports", [rear] + rear_posts)
rear_drills = []
for x, y in P["mounts"]:
    rear_drills += [cylinder("M2 clearance", x, y, -0.1,
                            P["screw_clearance_diameter"] / 2, seam + 0.2),
                    cone("90 degree countersink", x, y, 0,
                         P["rear_head_diameter"] / 2,
                         P["screw_clearance_diameter"] / 2,
                         P["rear_countersink_depth"])]
rear = cut("Rear screw holes", rear, fuse("Rear drilling tools", rear_drills))
rear = cut("01 Rear cover", rear, usb_tool())

# Main cup is open at the rear. The locating rim is relieved around the rear
# supports so it can slide into the tray without touching them.
front_blank = rounded("Front cup outside", 0, 0, seam, W, H,
                      face - seam, P["corner_radius"])
front_cavity = rounded("Electronics cavity", wall, wall, seam - 0.01,
                       W - 2 * wall, H - 2 * wall, inner - seam + 0.01,
                       P["corner_radius"] - wall)
front = cut("Front cup walls and face", front_blank, front_cavity)
rim_offset = P["rear_register_lip"] + P["register_clearance"]
rim_z = seam - P["register_depth"]
rim = rounded("Register outside", rim_offset, rim_offset, rim_z,
              W - 2 * rim_offset, H - 2 * rim_offset,
              P["register_depth"] + 0.02, P["corner_radius"] - rim_offset)
rim_inside = rounded("Register inside", rim_offset + P["register_wall"],
                     rim_offset + P["register_wall"], rim_z - 0.01,
                     W - 2 * (rim_offset + P["register_wall"]),
                     H - 2 * (rim_offset + P["register_wall"]),
                     P["register_depth"] + 0.04,
                     P["corner_radius"] - rim_offset - P["register_wall"])
rim = cut("Register wall", rim, rim_inside)
reliefs = [cylinder("Register post relief", x, y, rim_z - 0.1,
                    mount_r + 0.25, P["register_depth"] + 0.2)
           for x, y in P["mounts"]]
rim = cut("Register support clearances", rim, fuse("Register relief tools", reliefs))
posts = [cylinder("Front threaded boss", x, y, board_top,
                  mount_r, inner - board_top + 0.05) for x, y in P["mounts"]]
guides = []
for x in (wall, W - 2.25):
    for y in (8.0, 18.0):
        guides.append(box("PCB lateral guide", x, y, seam, 0.75, 4.0, 2.0))
for x in (3.3, 22.4):
    guides.append(box("PCB lower edge stop", x, wall, seam, 4.3, 0.75, 1.6))
front = fuse("Cup with rim bosses and guides", [front, rim] + posts + guides)
pilots = [cylinder("M2 pilot bore", x, y, board_top - 0.01,
                   P["screw_pilot_diameter"] / 2, P["screw_pilot_depth"] + 0.01)
          for x, y in P["mounts"]]
front = cut("Blind screw pilot holes", front, fuse("Pilot drill tools", pilots))
front = cut("USB cable clearance", front, usb_tool())
diffuser_stop_z = inner + P["diffuser_pocket_depth"]
front = cut("Diffuser back counterbore", front,
            cylinder("Diffuser pocket", cx, cy, inner - 0.01,
                     P["diffuser_pocket_diameter"] / 2,
                     P["diffuser_pocket_depth"] + 0.01))
front = cut("02 Front housing", front,
            cylinder("Optical aperture", cx, cy, diffuser_stop_z - 0.01,
                     P["lens_aperture_diameter"] / 2, face - diffuser_stop_z + 0.02))

# A separate hood prints upright on its annular base and bonds to the flat face.
hood_ring = cut("Hood annular blank",
                cylinder("Hood outside", cx, cy, face,
                         P["hood_outer_diameter"] / 2, Z - face),
                cylinder("Hood bore", cx, cy, face - 0.01,
                         P["hood_inner_diameter"] / 2, Z - face + 0.02))
hood_cut = box("Hood lower opening", cx - 7, cy - 7,
               face + P["hood_base_thickness"], 14,
               P["hood_lower_edge_y"] - cy + 7, Z - face)
hood = cut("03 Signal hood", hood_ring, hood_cut)
diffuser = cylinder("04 Opal diffuser", cx, cy,
                    diffuser_stop_z - P["diffuser_thickness"],
                    P["diffuser_diameter"] / 2, P["diffuser_thickness"])

reference = feature("Part::Feature", "REFERENCE - SL25 PCB with components")
reference.Shape = Part.read(str((ROOT / P["pcb_reference"]).resolve()))
reference.Placement.Base = App.Vector((W - 25) / 2, (H + 25) / 2, seam)
DOC.recompute()

fasteners = []
for index, (x, y) in enumerate(P["mounts"]):
    fastener = feature("Part::Feature", "REFERENCE - M2 x 10 CSK screw %d" % (index + 1))
    fastener.Shape = Part.makeCone(1.9, 1.0, 0.9, App.Vector(x, y, 0)).fuse(
        Part.makeCylinder(1, 9.1, App.Vector(x, y, 0.9)))
    fasteners.append(fastener)
DOC.recompute()

parts = {"01_rear_cover": rear, "02_front_housing": front,
         "03_signal_hood": hood, "04_diffuser": diffuser}
colors = {"01_rear_cover": [0.94, 0.69, 0.10], "02_front_housing": [0.19, 0.21, 0.23],
          "03_signal_hood": [0.11, 0.12, 0.13], "04_diffuser": [0.86, 0.94, 0.86]}
manifest = {"parts": {}, "reference": reference.Name,
            "fasteners": [obj.Name for obj in fasteners],
            "coordinate_system": "X right, Y up in front view, Z toward viewer. Rear at Z=0."}
report = {"units": "mm", "parts": {}, "intersections_mm3": {}, "clearances_mm": {}}
failures = []


def bounds(shape):
    b = shape.BoundBox
    return [round(v, 5) for v in [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]]


for name, obj in parts.items():
    shape = obj.Shape
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.04,
                                 AngularDeflection=0.14, Relative=False)
    # Orient each printing mesh on its largest intended bed face.
    print_mesh = Mesh.Mesh(mesh)
    if name == "02_front_housing":
        matrix = App.Matrix()
        matrix.rotateX(math.pi)
        print_mesh.transform(matrix)
    bb = print_mesh.BoundBox
    print_mesh.translate(-bb.XMin, -bb.YMin, -bb.ZMin)
    print_mesh.write(str(ROOT / "stl" / (name + ".stl")))
    Part.export([obj], str(ROOT / "cad" / (name + ".step")))
    mesh_ok = mesh.isSolid() and not mesh.hasNonManifolds()
    report["parts"][name] = {
        "valid_brep": shape.isValid(), "solid_count": len(shape.Solids),
        "volume_mm3": round(shape.Volume, 3), "assembly_bounds": bounds(shape),
        "mesh_watertight": mesh.isSolid(), "has_nonmanifold_edges": mesh.hasNonManifolds(),
        "facets": mesh.CountFacets, "print_bounds": bounds(print_mesh),
    }
    if not shape.isValid() or len(shape.Solids) != 1 or not mesh_ok:
        failures.append("Invalid solid or mesh: " + name)
    manifest["parts"][name] = {"object": obj.Name, "color": colors[name]}

for (a, ao), (b, bo) in itertools.combinations(parts.items(), 2):
    volume = ao.Shape.common(bo.Shape).Volume
    report["intersections_mm3"][a + " / " + b] = round(volume, 8)
    if volume > 1e-5:
        failures.append("Part interference: " + a + " / " + b)
for name, obj in parts.items():
    volume = obj.Shape.common(reference.Shape).Volume
    report["intersections_mm3"][name + " / PCB assembly"] = round(volume, 8)
    if volume > 1e-5:
        failures.append("PCB interference: " + name)

assembly = Part.makeCompound([obj.Shape for obj in parts.values()])
report["enclosure_bounds"] = bounds(assembly)
report["enclosure_size_mm"] = [round(assembly.BoundBox.XLength, 4),
                                round(assembly.BoundBox.YLength, 4),
                                round(assembly.BoundBox.ZLength, 4)]
if assembly.BoundBox.XLength > 30.00001 or assembly.BoundBox.YLength > 30.00001:
    failures.append("Front projection exceeds 30 mm")

# Use the required LED height, not just the generic KiCad model's shorter lens.
diffuser_back = diffuser_stop_z - P["diffuser_thickness"]
report["clearances_mm"] = {
    "bottom_component_to_floor": round(reference.Shape.BoundBox.ZMin - floor, 3),
    "required_LED_tip_to_diffuser": round(diffuser_back - (board_top + 12.5), 3),
    "diffuser_radial_fit": (P["diffuser_pocket_diameter"] - P["diffuser_diameter"]) / 2,
    "rear_register_per_side": P["register_clearance"],
    "pcb_to_side_guides_per_side": 0.25,
    "screw_nominal_engagement": round(10 - board_top, 3),
    "screw_tip_to_blind_bore_end": round(board_top + P["screw_pilot_depth"] - 10, 3),
}

# Sweep the PCB and rear cover away from the front housing along the assembly
# direction. A pin through a drilled pilot is intentionally omitted here.
report["rear_removal_sweep"] = []
for distance in (0.2, 1, 2, 4, 8, 16, 25):
    moved_rear, moved_pcb = rear.Shape.copy(), reference.Shape.copy()
    moved_rear.translate(App.Vector(0, 0, -distance))
    moved_pcb.translate(App.Vector(0, 0, -distance))
    volume = front.Shape.common(moved_rear).Volume + front.Shape.common(moved_pcb).Volume
    report["rear_removal_sweep"].append({"distance": distance, "interference_mm3": round(volume, 8)})
    if volume > 1e-5:
        failures.append("Assembly path blocked at " + str(distance))

plug = Part.makeBox(12, 8, 6, App.Vector(cx - 6, -5.6, P["usb_center_z"] - 3))
report["usb_overmold_envelope"] = {"size": [12, 8, 6], "inboard_end_y": 2.4,
                                  "interference_mm3": round(plug.common(assembly).Volume, 8),
                                  "pcb_interference_mm3": round(plug.common(reference.Shape).Volume, 8)}
if plug.common(assembly).Volume > 1e-5 or plug.common(reference.Shape).Volume > 1e-5:
    failures.append("USB overmold envelope obstructed")

report["assumptions"] = [
    "Single RGB optical window; three independent lamps would require a PCB revision.",
    "Depth 25 mm is a design assumption; only the 30 x 30 mm front limit was fixed.",
    "Generic PCB STEP is a reference; actual PCB thickness modeled nominally as 1.6 mm.",
    "Diffuser and hood retained by small adhesive beads; not snap fits.",
    "M2 x 10 countersunk screws, 90 degrees, max head diameter 4.0 mm; tap or form the plastic pilot holes.",
    "Screw threads deliberately overlap pilot material; thread geometry is not simulated.",
    "USB cable overmold target <=12 x 6 mm. Check actual plug insertion and shoulder clearance.",
    "No printed fit, load, optical, thermal, or ingress testing has been performed."
]
report["failures"] = failures
report["passed"] = not failures

metadata = DOC.addObject("App::FeaturePython", "DesignNotes")
metadata.Label = "Design parameters - regenerate with build.py"
metadata.addProperty("App::PropertyString", "Revision").Revision = "A"
metadata.addProperty("App::PropertyString", "Units").Units = "mm"
metadata.addProperty("App::PropertyString", "ParametersJSON").ParametersJSON = json.dumps(P)
metadata.addProperty("App::PropertyStringList", "Assumptions").Assumptions = report["assumptions"]

# Store scene geometry for deterministic, non-GUI technical renders.
scene = []
for name, obj in parts.items():
    vertices, faces = obj.Shape.tessellate(0.10)
    scene.append({"name": name, "color": colors[name],
                  "vertices": [[v.x, v.y, v.z] for v in vertices], "faces": faces})
for index, solid in enumerate(reference.Shape.Solids):
    color = [0.10, 0.42, 0.25] if index == 54 else [0.67, 0.70, 0.73]
    if index in (4, 52):
        color = [0.19, 0.20, 0.22]
    if index == 6:
        color = [0.63, 0.77, 0.83]
    vertices, faces = solid.tessellate(0.13)
    scene.append({"name": "pcb_%02d" % index, "color": color,
                  "vertices": [[v.x, v.y, v.z] for v in vertices], "faces": faces})
for obj in fasteners:
    vertices, faces = obj.Shape.tessellate(0.13)
    scene.append({"name": "screw", "color": [0.65, 0.68, 0.71],
                  "vertices": [[v.x, v.y, v.z] for v in vertices], "faces": faces})

(ROOT / "preview/scene.json").write_text(json.dumps(scene), encoding="utf-8")
(ROOT / "checks/validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
(ROOT / "cad/objects.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
DOC.recompute()
DOC.saveAs(str(ROOT / "cad/SL25_Traffic_A.FCStd"))
Part.export(list(parts.values()) + [reference] + fasteners,
            str(ROOT / "cad/SL25_Traffic_A_assembly.step"))
print(json.dumps({"passed": report["passed"], "failures": failures,
                  "dimensions": report["enclosure_size_mm"],
                  "clearances": report["clearances_mm"]}, indent=2))
if failures:
    sys.exit(1)
