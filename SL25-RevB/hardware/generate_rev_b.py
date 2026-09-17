"""SL25 Rev B: centered 5050 RGB source, electronics and USB on the back."""
import copy
import json
from pathlib import Path
import pcbnew as pcb
import generate_board as g

g.OUT = Path(__file__).resolve().parent / "sl25_rev_b"
g.REVISION = "B"
old = {p["ref"]: copy.deepcopy(p) for p in g.parts}
g.parts = []
g.SYMS["SmartRGB"] = g.box_pins(
    [(1, "VDD", "power_in"), (4, "DIN", "input"), (3, "GND", "power_in")],
    [(2, "DOUT", "output")])
del g.SYMS["RGB"]
placements = {
    "J1": (112.5, 121.15), "U1": (112.5, 106.8), "U2": (112.5, 114.1),
    "D1": (112.5, 112.5), "R1": (120.2, 117.4), "R2": (105.1, 117.4),
    "R3": (120.7, 105.5), "R4": (120.7, 108.5), "R6": (120.7, 111.5),
    "R7": (103.5, 107.8), "C1": (108.5, 111.8), "C2": (105.3, 111.0),
    "C3": (121.0, 121.0), "C4": (108.3, 114.7), "JP1": (120.7, 114.4),
}
for ref, p in old.items():
    if ref == "R5":
        continue
    p["xy"] = placements.get(ref, p["xy"])
    p["back"] = ref not in ("D1", "H1", "H2")
    if ref == "C2":
        p["angle"] = 90
    if ref == "U1":
        p["nets"].update({"3": "LED_DATA_RAW", "11": None, "9": None})
        p["note"] = "Bottom side CH552G SOP16. P1.5 sends 800kbit/s GRB; Rev A PWM firmware is incompatible."
    elif ref == "J1":
        p["note"] = "Bottom side, opens toward PCB +Y. Exact GCT USB4105-GF-A footprint required."
    elif ref == "D1":
        p.update(kind="SmartRGB", value="WS2812B-V5", angle=180,
                 fp="LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm",
                 nets={"1": "+5V", "2": None, "3": "GND", "4": "LED_DATA"},
                 mpn="Worldsemi WS2812B-V5, 5050 PLCC4",
                 note="Centered at PCB (12.5,12.5). 1=VDD,2=DOUT NC,3=GND,4=DIN; corner notch at pin 3. GRB 800kbit/s, reset low >280us. Not the Rev A through-hole LED.")
    elif ref == "R3":
        p.update(value="330", mpn="0805 330 ohm 1% >=0.125W",
                 nets={"1": "LED_DATA_RAW", "2": "LED_DATA"}, note="DIN series resistor; not an LED current limiter.")
    elif ref == "R4":
        p.update(value="100k", mpn="0805 100k 1% >=0.125W",
                 nets={"1": "LED_DATA", "2": "GND"}, note="DIN idle pull-down.")
    elif ref == "C3":
        p.update(value="4.7uF", mpn="0805 4.7uF X7R 16V", note="USB input bulk decoupling; total nominal rail capacitance 5.0uF.")
    g.parts.append(p)
g.part("C5", "C", "100nF", g.cap_fp, (117.2, 113.3), (241.3, 91.44),
       {1: "+5V", 2: "GND"}, back=True, angle=90, mpn="0805 100nF X7R 16V",
       note="Local RGB LED supply bypass, bottom side near D1 pin 1 via.")
g.SCHEMATIC_NOTES = [
    ("USB-C: bottom-mounted, independent 5.1k CC resistors", 23, 20),
    ("CH552G: internal oscillator, 5V logic", 111, 20),
    ("Centered 5050 RGB / internal current driver", 193, 20),
    ("REV B: LED_DATA_RAW = P1.5 / pin 3. 24-bit GRB at 800kbit/s; low reset >280us.", 23, 174),
    ("D1: 1=5V, 2=DOUT unconnected, 3=GND, 4=DIN. Use exact WS2812B-V5 pinout.", 23, 180),
    ("JP1: temporary USB ISP strap. Prototype: not bench-tested; firmware and host software separate.", 23, 186),
]
g.BOARD_TEXT = [("SL25 REV B", 112.5, 102.3, pcb.F_SilkS),
                ("CENTER RGB", 112.5, 121.0, pcb.F_SilkS),
                ("BOOT", 120.7, 116.0, pcb.B_SilkS),
                ("5V", 103.0, 123.0, pcb.B_SilkS),
                ("GND", 105.5, 123.0, pcb.B_SilkS)]

g.OUT.mkdir(parents=True, exist_ok=True)
g.metadata()
g.schematic()
board, fps, nets = g.make_board()
references = {
    "D1": (112.5, 108.8), "U1": (112.5, 106.8), "U2": (115.5, 113.6),
    "R1": (120.2, 118.7), "R2": (105.1, 118.7), "R3": (120.7, 104.15),
    "R4": (120.7, 107.15), "R6": (120.7, 110.15), "R7": (103.5, 106.45),
    "C1": (108.5, 113.1), "C2": (103.0, 111.0), "C3": (121, 122.35),
    "C4": (108.3, 116.0), "C5": (117.2, 110.8), "JP1": (123.4, 114.4),
    "J1": (112.5, 121),
}
for ref, fp in fps.items():
    fp.Reference().SetTextSize(g.vec(.8, .8))
    fp.Reference().SetTextThickness(pcb.FromMM(.10))
    fp.Reference().SetTextAngle(pcb.EDA_ANGLE(0, pcb.DEGREES_T))
    if ref.startswith("TP"):
        fp.Reference().SetVisible(ref not in ("TP1", "TP2"))
        x, y = pcb.ToMM(fp.GetPosition())
        fp.Reference().SetPosition(g.vec(x, 100.6 if ref in ("TP4", "TP5") else 100.75))
    elif ref in references:
        fp.Reference().SetPosition(g.vec(*references[ref]))
pcb.SaveBoard(str(g.OUT / "sl25.kicad_pcb"), board)
print("Rev B generated:", g.OUT)
print("U1 power pads:", [(p.GetNumber(), tuple(pcb.ToMM(p.GetPosition())))
                         for p in fps["U1"].Pads() if p.GetNumber() in ("14", "15", "16")])
