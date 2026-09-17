"""Verify schematic/PCB/optical interface invariants for the coordinated Rev B."""
from pathlib import Path
import hashlib
import json
import math
import pcbnew as pcb

root = Path(__file__).resolve().parent / "sl25_rev_b"
board = pcb.LoadBoard(str(root / "sl25.kicad_pcb"))
fps = {f.GetReference(): f for f in board.GetFootprints()}


def net(ref, pin):
    values = {p.GetNetname().lstrip('/') for p in fps[ref].Pads() if p.GetNumber() == str(pin)}
    assert len(values) == 1, (ref, pin, values)
    return values.pop()


for pin, expected in {3: "LED_DATA_RAW", 12: "USB_DP", 13: "USB_DM", 14: "GND",
                      15: "+5V", 16: "V33", 6: "RESET", 2: "PROG_SCS",
                      4: "PROG_MISO", 5: "PROG_SCK"}.items():
    assert net("U1", pin) == expected
for pin, expected in {1: "+5V", 3: "GND", 4: "LED_DATA"}.items():
    assert net("D1", pin) == expected
assert net("D1", 2).startswith("unconnected-")
assert fps["D1"].GetValue() == "WS2812B-V5"
assert fps["D1"].GetLayer() == pcb.F_Cu
assert abs(fps["D1"].GetOrientationDegrees() - 180) < 1e-6
assert math.dist(tuple(pcb.ToMM(fps["D1"].GetPosition())), (112.5, 112.5)) < 1e-6
for ref, fp in fps.items():
    if ref not in ("D1", "H1", "H2"):
        assert fp.GetLayer() == pcb.B_Cu, ref
assert net("R3", 1) == "LED_DATA_RAW" and net("R3", 2) == "LED_DATA"
assert fps["R3"].GetValue() == "330"
assert net("R4", 1) == "LED_DATA" and net("R4", 2) == "GND"
assert fps["R4"].GetValue() == "100k" and "R5" not in fps
for ref in ("C1", "C3", "C4", "C5"):
    assert net(ref, 1) == "+5V" and net(ref, 2) == "GND"
assert net("C2", 1) == "V33" and net("C2", 2) == "GND"
assert fps["C3"].GetValue() == "4.7uF"
for pin, expected in {"A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM",
                      "A5": "CC1", "B5": "CC2", "SH": "GND"}.items():
    assert net("J1", pin) == expected
assert net("R1", 1) == "CC1" and net("R2", 1) == "CC2"
assert net("R1", 2) == net("R2", 2) == "GND"
assert net("R6", 1) == "+5V" and net("R6", 2) == net("JP1", 1) == "BOOT_PULL"
assert net("JP1", 2) == "USB_DP"
assert net("R7", 1) == "RESET" and net("R7", 2) == "GND"
assert board.GetCopperLayerCount() == 2
assert abs(pcb.ToMM(board.GetDesignSettings().GetBoardThickness()) - 1.6) < 1e-6
for ref, position in [("H1", (102.7, 102.7)), ("H2", (122.3, 102.7))]:
    assert math.dist(tuple(pcb.ToMM(fps[ref].GetPosition())), position) < 1e-6
    assert abs(pcb.ToMM(next(iter(fps[ref].Pads())).GetDrillSize().x) - 2.2) < 1e-6
for fp in fps.values():
    for model in fp.Models():
        assert model.m_Filename.startswith("${KIPRJMOD}/models/")
        assert (root / model.m_Filename.replace("${KIPRJMOD}/", "")).is_file()
for phrase in ("Found 0 DRC violations", "Found 0 unconnected pads", "Found 0 Footprint errors"):
    assert phrase in (root / "checks/drc.rpt").read_text(encoding="utf-8")
erc = (root / "checks/erc.rpt").read_text(encoding="utf-8")
assert "Errors 0" in erc and "Warnings 0" in erc
for name in ("sl25-PTH.drl", "sl25-NPTH.drl", "sl25-F_Cu.gtl", "sl25-B_Cu.gbl", "sl25-Edge_Cuts.gm1"):
    assert (root / "fabrication" / name).stat().st_size > 100
step = (root / "mechanical/sl25.step").read_text(encoding="utf-8")
assert "LED_WS2812B_PLCC4" in step and "SOIC-16_3.9x9.9mm" in step
parameters = json.loads((root.parents[1] / "enclosure/sl25_traffic_rev_b/parameters.json").read_text())
assert parameters["lens_center"] == [15, 15]
assert parameters["lens_aperture_diameter"] == 24

interface = {
    "revision": "B", "units": "mm",
    "coordinate_convention": "PCB top view; origin at top-left; x right, y down",
    "board": {"width": 25, "height": 25, "thickness": 1.6, "corner_radius": 1},
    "enclosure": {"width": 30, "height": 30, "depth_including_hood": 30},
    "mounting_holes": [{"ref": ref, "x": x, "y": 2.7, "diameter": 2.2}
                       for ref, x in [("H1", 2.7), ("H2", 22.3)]],
    "led": {"ref": "D1", "mpn": "WS2812B-V5", "side": "top", "optical_center": [12.5, 12.5],
            "body_size": [5.4, 5.0, 1.57], "height_allowance_above_pcb": 1.7,
            "rotation_degrees": 180, "pin3_notch_in_board_top_view": "upper-left"},
    "usb": {"ref": "J1", "mpn": "GCT USB4105-GF-A", "side": "bottom",
            "footprint_origin": [12.5, 21.15], "insertion_direction": "+Y",
            "clearance_below_pcb_min": 3.5},
    "optics": {"aperture_diameter": 24, "film_diameter": 26, "film_thickness": 0.2,
               "clear_PC_thickness": 0.5, "minimum_LED_to_film": 13.5,
               "enclosure_center": [15, 15]},
    "notes": ["Use only with Rev B enclosure.", "Geometry validated; no physical or optical test performed."]
}
(root / "mechanical/interface.json").write_text(json.dumps(interface, indent=2), encoding="utf-8")
result = {"revision": "B", "tool": pcb.Version(), "passed": True, "footprints": len(fps),
          "board_mm": [25, 25, 1.6], "copper_layers": 2,
          "erc_errors": 0, "erc_warnings": 0, "drc_violations": 0, "unconnected_pads": 0,
          "schematic_parity_issues": 0, "centered_source": True, "top_electronic_parts": ["D1"],
          "critical_pinmap_checks": "passed", "physical_validation": "not performed",
          "pcb_sha256": hashlib.sha256((root / "sl25.kicad_pcb").read_bytes()).hexdigest()}
(root / "checks/verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
