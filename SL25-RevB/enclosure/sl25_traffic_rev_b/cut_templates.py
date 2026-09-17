"""Generate millimeter SVG cut contours for the purchased optical sheets."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
p = json.loads((root / "parameters.json").read_text())
out = root / "cut_templates"
out.mkdir(exist_ok=True)
ns = "http://www.w3.org/2000/svg"
ET.register_namespace("", ns)


def svg(width, height):
    return ET.Element("{%s}svg" % ns, width=str(width) + "mm", height=str(height) + "mm",
                      viewBox="0 0 %s %s" % (width, height))


def circle(parent, x, y, diameter):
    ET.SubElement(parent, "{%s}circle" % ns, cx=str(x), cy=str(y), r=str(diameter / 2),
                  fill="none", stroke="black", **{"stroke-width": "0.05"})


for name, inner in [("05_PET_diffusion_film_OD26_T0.2", None),
                    ("06_clear_PC_OD26_T0.5", None),
                    ("07_foam_ring_OD26_ID24_T0.5", p["lens_aperture_diameter"])]:
    drawing = svg(28, 28)
    circle(drawing, 14, 14, p["diffuser_diameter"])
    if inner:
        circle(drawing, 14, 14, inner)
    ET.ElementTree(drawing).write(out / (name + ".svg"), encoding="utf-8", xml_declaration=True)

sheet = svg(112, 60)
for x, name, thickness, inner in [(17, "PET diffuser", "0.2 mm", None),
                                 (53, "Clear PC", "0.5 mm", None),
                                 (89, "Foam gasket", "0.5 mm free", 24)]:
    circle(sheet, x, 19, 26)
    if inner:
        circle(sheet, x, 19, inner)
    for y, label in ((37, name), (42, thickness), (47, "OD 26 mm" + (" / ID 24" if inner else ""))):
        text = ET.SubElement(sheet, "{%s}text" % ns, x=str(x), y=str(y),
                             **{"font-size": "2.5", "font-family": "Arial", "text-anchor": "middle"})
        text.text = label
ET.SubElement(sheet, "{%s}rect" % ns, x="3", y="49", width="10", height="10",
              fill="none", stroke="black", **{"stroke-width": "0.05"})
text = ET.SubElement(sheet, "{%s}text" % ns, x="16", y="56", **{"font-size": "2.5", "font-family": "Arial"})
text.text = "Print at 100%. Check the 10 x 10 mm calibration square."
ET.ElementTree(sheet).write(out / "optical_sheet_1to1.svg", encoding="utf-8", xml_declaration=True)
print("Generated 3 cut contours and a 1:1 calibration sheet.")
