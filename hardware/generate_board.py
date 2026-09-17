"""Rebuild the SL25 prototype in KiCad's bundled Python (pcbnew required)."""
from pathlib import Path
import csv
import json
import math
import os
import subprocess
import uuid
import xml.etree.ElementTree as ET
import pcbnew as pcb

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "sl25"
LIB = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "E:/Kicard/share/kicad/footprints"))
NAME = "sl25"
REVISION = "A"
SCHEMATIC_NOTES = None
BOARD_TEXT = None
NS = uuid.UUID("5a8e4c42-de27-4d84-90f6-7883a3b62e90")
uid = lambda s: str(uuid.uuid5(NS, s))
SHEET = uid("sheet")


def quote(s):
    return json.dumps(str(s), ensure_ascii=True)


def pin(num, name, x, y, angle, kind="passive"):
    return dict(num=str(num), name=name, x=x, y=y, angle=angle, kind=kind)


def box_pins(left, right):
    result = []
    for side, items in [(0, left), (1, right)]:
        for i, item in enumerate(items):
            n, name, kind = item
            result.append(pin(n, name, -15.24 if not side else 15.24,
                              (len(items)-1)*2.54-i*5.08, 0 if not side else 180, kind))
    return result


SYMS = {
    "R": [pin(1, "~", -5.08, 0, 0), pin(2, "~", 5.08, 0, 180)],
    "C": [pin(1, "~", -5.08, 0, 0), pin(2, "~", 5.08, 0, 180)],
    "Jumper": [pin(1, "~", -5.08, 0, 0), pin(2, "~", 5.08, 0, 180)],
    "TestPoint": [pin(1, "~", 0, 0, 90)],
    "Mount": [],
    "PowerFlag": [pin(1, "~", 0, 0, 90, "power_out")],
    "CH552G": box_pins(
        [(15,"VCC","power_in"),(16,"V33","power_out"),(14,"GND","power_in"),
         (12,"P3.6 / USB_D+","bidirectional"),(13,"P3.7 / USB_D-","bidirectional"),
         (6,"RST (active high)","input"),(7,"P3.1 / TXD","bidirectional"),(8,"P3.0 / RXD","bidirectional")],
        [(3,"P1.5 / PWM1","bidirectional"),(11,"P3.4 / PWM2","bidirectional"),(9,"P1.1","bidirectional"),
         (2,"P1.4 / SCS","bidirectional"),(4,"P1.6 / MISO","bidirectional"),(5,"P1.7 / SCK","bidirectional"),
         (1,"P3.2","bidirectional"),(10,"P3.3","bidirectional")]),
    "USB_C": box_pins(
        [(n,n,"passive") for n in ["A1","A12","B1","B12","SH","A8","B8"]],
        [(n,n,"passive") for n in ["A4","A9","B4","B9","A5","B5","A6","B6","A7","B7"]]),
    "USBLC6": box_pins([(1,"I/O1","passive"),(2,"GND","power_in"),(3,"I/O2","passive")],
                           [(6,"I/O1","passive"),(5,"VBUS","power_in"),(4,"I/O2","passive")]),
    "RGB": [pin(1,"RED",-10.16,5.08,0), pin(3,"BLUE",-10.16,0,0),
            pin(4,"GREEN",-10.16,-5.08,0), pin(2,"COMMON K",10.16,0,180)],
}

parts = []


def part(ref, kind, value, fp, xy, sch, nets, angle=0, back=False, mpn="", note=""):
    p = dict(ref=ref, kind=kind, value=value, fp=fp, xy=xy, sch=sch,
             nets={str(k):v for k,v in nets.items()}, angle=angle, back=back,
             mpn=mpn or value, note=note, uuid=uid(ref))
    parts.append(p)
    return p


res_fp = "Resistor_SMD:R_0805_2012Metric"
cap_fp = "Capacitor_SMD:C_0805_2012Metric"
tp_fp = "TestPoint:TestPoint_Pad_D1.0mm"
part("J1","USB_C","USB-C USB2.0","Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
     (112.5,121.15),(43.18,53.34),
     dict(A1="GND",A12="GND",B1="GND",B12="GND",SH="GND",A4="+5V",A9="+5V",B4="+5V",B9="+5V",
          A5="CC1",B5="CC2",A6="USB_DP",B6="USB_DP",A7="USB_DM",B7="USB_DM",A8=None,B8=None),
     mpn="GCT USB4105-GF-A",note="Exact footprint required; USB-C socket is not interchangeable by appearance.")
part("U1","CH552G","CH552G","Package_SO:SOIC-16_3.9x9.9mm_P1.27mm",
     (112.5,110.7),(134.62,58.42),
     {15:"+5V",16:"V33",14:"GND",12:"USB_DP",13:"USB_DM",6:"RESET",7:None,8:None,
      3:"PWM_RED",11:"PWM_GREEN",9:"GPIO_BLUE",2:"PROG_SCS",4:"PROG_MISO",5:"PROG_SCK",1:None,10:None},
     angle=270,note="SOP16 150mil. Buy with factory USB ISP bootloader; do not substitute CH552T/E/P.")
part("U2","USBLC6","USBLC6-2SC6","Package_TO_SOT_SMD:SOT-23-6",
     (112.5,114.7),(43.18,104.14),{1:"USB_DP",6:"USB_DP",3:"USB_DM",4:"USB_DM",2:"GND",5:"+5V"},
     angle=270,back=True,note="Bottom side; pins 1/6 and 3/4 are internally connected line pairs.")
part("D1","RGB","WP154A4SUREQBFZGC","LED_THT:LED_D5.0mm-4_RGB_Wide_Pins",
     (109.2615,103.5),(241.3,53.34),{1:"LED_RED",2:"GND",3:"LED_BLUE",4:"LED_GREEN"},
     note="Form 1.27mm native leads to 2.159mm PCB pitch with 3mm standoff. 1=R, 2=common K, 3=B, 4=G. Clear lens needs diffuser.")
for ref,value,xy,sch,nets in [
    ("R1","5.1k",(105.1,117.4),(43.18,137.16),{1:"CC1",2:"GND"}),
    ("R2","5.1k",(120.2,117.4),(43.18,149.86),{1:"CC2",2:"GND"}),
    ("R3","1k",(103.0,108.4),(200.66,40.64),{1:"PWM_RED",2:"LED_RED"}),
    ("R4","1k",(103.0,111.5),(200.66,66.04),{1:"PWM_GREEN",2:"LED_GREEN"}),
    ("R5","1k",(103.0,114.6),(200.66,53.34),{1:"GPIO_BLUE",2:"LED_BLUE"}),
    ("R6","10k",(120.7,114.4),(134.62,137.16),{1:"+5V",2:"BOOT_PULL"}),
    ("R7","10k",(106.5,105.4),(134.62,149.86),{1:"RESET",2:"GND"}),
]:
    part(ref,"R",value,res_fp,xy,sch,nets,mpn=f"0805 {value} 1% >=0.125W")
for ref,value,xy,sch,nets in [
    ("C1","100nF",(120.7,111.1),(134.62,101.6),{1:"+5V",2:"GND"}),
    ("C2","100nF",(120.7,108.0),(134.62,114.3),{1:"V33",2:"GND"}),
    ("C3","1uF",(121.0,121.0),(43.18,162.56),{1:"+5V",2:"GND"}),
    ("C4","100nF",(108.7,114.7),(43.18,119.38),{1:"+5V",2:"GND"}),
]:
    part(ref,"C",value,cap_fp,xy,sch,nets,back=(ref=="C4"),mpn=f"0805 {value} X7R 16V")
part("JP1","Jumper","BOOT (normally open)","Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
     (120.7,114.4),(170.18,137.16),{1:"BOOT_PULL",2:"USB_DP"},back=True,
     mpn="PCB touch pads",note="Momentarily bridge during USB insertion; release after ISP enumeration. Do not solder closed.")
for i,(net,xy) in enumerate([("+5V",(103,121.5)),("GND",(105,121.5)),("PROG_SCS",(106.5,102.0)),
                            ("PROG_MISO",(109.0,101.8)),("PROG_SCK",(116.0,101.8)),("RESET",(118.5,102.0))],1):
    part(f"TP{i}","TestPoint",net,tp_fp,xy,(195.58+(i-1)%3*25.4,111.76+(i-1)//3*15.24),{1:net},back=True,
         mpn="PCB test pad",note="Programmer pads use 5V signaling; disconnect USB before external power.")
for i,x in enumerate([102.7,122.3],1):
    part(f"H{i}","Mount","M2 / 2.2mm","MountingHole:MountingHole_2.2mm_M2",(x,102.7),
         (200.66+(i-1)*25.4,157.48),{},mpn="M2 mounting hole")


def effects(size=1.0, extra=""):
    return f'(effects (font (size {size} {size})) {extra})'


def symbol_def(kind):
    pins=SYMS[kind]
    if kind in ("R","C","Jumper"):
        w,h=2.54,1.0
    elif kind=="RGB": w,h=7.62,7.62
    elif kind in ("TestPoint","PowerFlag","Mount"): w,h=1.27,1.27
    else: w,h=12.7,max(abs(p["y"]) for p in pins)+2.54
    ref={"R":"R","C":"C","RGB":"D","USB_C":"J","Jumper":"JP","TestPoint":"TP","PowerFlag":"#FLG","Mount":"H"}.get(kind,"U")
    s=[f'(symbol "SL25:{kind}" (pin_names (offset 0.762)) (in_bom yes) (on_board yes)',
       f'(property "Reference" "{ref}" (at 0 {h+2.54} 0) {effects()})',
       f'(property "Value" "{kind}" (at 0 {-h-2.54} 0) {effects()})',
       f'(symbol "{kind}_0_1"']
    if kind=="C":
        for x in [-.635,.635]:
            s.append(f'(polyline (pts (xy {x} -1.905) (xy {x} 1.905)) (stroke (width 0.254) (type default)) (fill (type none)))')
    elif kind in ("TestPoint","PowerFlag","Mount"):
        s.append('(circle (center 0 1.27) (radius 1.0) (stroke (width 0.254) (type default)) (fill (type none)))')
    elif kind=="Jumper":
        for x in [-1.27,1.27]:
            s.append(f'(circle (center {x} 0) (radius 0.635) (stroke (width 0.254) (type default)) (fill (type none)))')
    else:
        s.append(f'(rectangle (start {-w} {h}) (end {w} {-h}) (stroke (width 0.254) (type default)) (fill (type background)))')
    s.append(f') (symbol "{kind}_1_1"')
    for p in pins:
        length=2.54
        if kind=="C": length=4.445
        if kind=="Jumper": length=3.175
        if kind in ("TestPoint","PowerFlag"): length=0
        s.append(f'(pin {p["kind"]} line (at {p["x"]} {p["y"]} {p["angle"]}) (length {length}) '
                 f'(name {quote(p["name"])} {effects()}) (number {quote(p["num"])} {effects()}))')
    return "\n".join(s)+"))"


def schematic():
    s=[f'(kicad_sch (version 20250114) (generator "eeschema") (uuid "{SHEET}") (paper "A4")',
       f'(title_block (title "SL25 - USB status light") (date "2026-09-05") (rev "{REVISION}") '
       '(company "25 x 25 mm / 30 x 30 mm enclosure target"))',
       '(lib_symbols '+"\n".join(symbol_def(k) for k in SYMS)+')']
    allparts=parts+[dict(ref="#FLG01",kind="PowerFlag",value="PWR_FLAG",sch=(76.2,162.56),fp="",nets={"1":"+5V"},uuid=uid("flg1")),
                    dict(ref="#FLG02",kind="PowerFlag",value="PWR_FLAG",sch=(76.2,149.86),fp="",nets={"1":"GND"},uuid=uid("flg2"))]
    for p in allparts:
        x,y=p["sch"]; kind=p["kind"]
        pins=SYMS[kind]
        h=max([abs(pn["y"]) for pn in pins]+[1.27])+2.54
        val=p["value"]
        s.append(f'(symbol (lib_id "SL25:{kind}") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{p["uuid"]}") '
                 f'(property "Reference" {quote(p["ref"])} (at {x} {y-h-3.81} 0) {effects(1.27)}) '
                 f'(property "Value" {quote(val)} (at {x} {y-h-1.27} 0) {effects(1.0)}) '
                 f'(property "Footprint" {quote("SL25:"+p["fp"].split(":")[-1] if p["fp"] else "")} (at {x} {y} 0) {effects(1,"(hide yes)")}) '
                 f'(instances (project "{NAME}" (path "/{SHEET}" (reference {quote(p["ref"])}) (unit 1)))) )')
        for pn in pins:
            px,py=round(x+pn["x"],4),round(y-pn["y"],4)
            net=p["nets"].get(pn["num"])
            key=p["ref"]+"/"+pn["num"]
            if net is None:
                s.append(f'(no_connect (at {px} {py}) (uuid "{uid(key+"nc")}"))')
                continue
            dx=-7.62 if pn["angle"]==0 else 7.62 if pn["angle"]==180 else 0
            dy=5.08 if pn["angle"]==90 else 0
            lx,ly=round(px+dx,4),round(py+dy,4)
            s.append(f'(wire (pts (xy {px} {py}) (xy {lx} {ly})) (stroke (width 0) (type default)) (uuid "{uid(key+"wire")}"))')
            s.append(f'(label {quote(net)} (at {lx} {ly} {180 if dx<0 else 0}) {effects(.95,"(justify left bottom)")} (uuid "{uid(key+"label")}"))')
    for text,x,y in (SCHEMATIC_NOTES or [("USB-C: independent 5.1k CC pull-downs; shield to GND",23,20),
                     ("CH552G: internal oscillator and USB pull-up",111,20),
                     ("LED current limited to < 6 mA per GPIO",193,20),
                     ("USB ISP: bridge JP1 while plugging USB, then release.",23,174),
                     ("Prototype: not bench-tested. Firmware / host agent supplied separately.",23,180),
                     ("D1: exact pin order 1=R / 2=K / 3=B / 4=G; do not fit common-anode LED.",23,186)]):
        s.append(f'(text {quote(text)} (at {x} {y} 0) {effects(1.15,"(justify left)")} (uuid "{uid(text)}"))')
    s.append('(embedded_fonts no))')
    (OUT/f"{NAME}.kicad_sch").write_text("\n".join(s),encoding="utf-8")
    defs="\n".join(symbol_def(k).replace(f'"SL25:{k}"',f'"{k}"',1) for k in SYMS)
    (OUT/"SL25.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+defs+")",encoding="utf-8")
    (OUT/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "SL25") (type "KiCad") (uri "${KIPRJMOD}/SL25.kicad_sym") (options "") (descr "SL25 verified pin maps")))',encoding="utf-8")


def vec(x,y): return pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))


def make_board():
    b=pcb.BOARD(); b.SetCopperLayerCount(2)
    b.GetTitleBlock().SetRevision(REVISION)
    b.GetTitleBlock().SetTitle("SL25 USB status light")
    b.GetDesignSettings().SetBoardThickness(pcb.FromMM(1.6))
    cli=Path(pcb.__file__).parents[2]/"kicad-cli.exe"
    subprocess.run([str(cli),"sch","export","netlist","--format","kicadxml","-o",str(OUT/"sl25.net"),str(OUT/"sl25.kicad_sch")],check=True)
    xml=ET.parse(OUT/"sl25.net")
    padnets={}
    for n in xml.findall("./nets/net"):
        for node in n.findall("node"):padnets[(node.attrib["ref"],node.attrib["pin"])]=n.attrib["name"]
    netnames=sorted(set(padnets.values()))
    nets={}
    for name in netnames:
        n=pcb.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
    fplib=OUT/"SL25.pretty";fplib.mkdir(exist_ok=True)
    fps={}
    for p in parts:
        lib,name=p["fp"].split(":")
        fp=pcb.FootprintLoad(str(LIB/(lib+".pretty")),name)
        if not fp: raise RuntimeError(p["fp"])
        # Local footprint library makes the editable project independent of installed libraries.
        target=fplib/(name+".kicad_mod")
        source=(LIB/(lib+".pretty")/(name+".kicad_mod")).read_text(encoding="utf-8")
        # Remove the receptacle's overhanging silk strokes; retain fab and courtyard geometry.
        if p["ref"]=="J1":
            for item in list(fp.GraphicalItems()):
                if item.GetLayer()==pcb.F_SilkS and item.GetBoundingBox().GetBottom()>pcb.FromMM(3.4):fp.Remove(item)
        pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(fplib),fp)
        fp.SetFPID(pcb.LIB_ID("SL25",name))
        fp.SetReference(p["ref"]);fp.SetValue(p["value"])
        fp.SetAttributes(fp.GetAttributes() & ~pcb.FP_EXCLUDE_FROM_BOM)
        fp.SetPath(pcb.KIID_PATH("/"+SHEET+"/"+p["uuid"]))
        b.Add(fp)
        fp.SetPosition(vec(*p["xy"]))
        fp.SetOrientationDegrees(p["angle"])
        if p["back"]: fp.Flip(fp.GetPosition(),False)
        fp.Reference().SetTextSize(vec(.8,.8));fp.Reference().SetTextThickness(pcb.FromMM(.12))
        if p["ref"] in ["H1","H2"]:fp.Reference().SetVisible(False)
        if p["ref"]=="D1":fp.Reference().SetPosition(vec(118.6,105.3))
        if p["ref"] in ["TP3","TP4","TP5","TP6"]:
            x,y=p["xy"];fp.Reference().SetPosition(vec(x,105.3))
        if p["ref"]=="U2":fp.Reference().SetPosition(vec(114.9,114.6));fp.Reference().SetTextAngle(pcb.EDA_ANGLE(90,pcb.DEGREES_T))
        fp.Value().SetVisible(False)
        for pad in fp.Pads():
            n=padnets.get((p["ref"],pad.GetNumber()))
            if n: pad.SetNet(nets[n])
        fps[p["ref"]]=fp
    # Rounded 25 mm square, with M2 holes along the top edge.
    for a,z in [((101,100),(124,100)),((125,101),(125,124)),((124,125),(101,125)),((100,124),(100,101))]:
        sh=pcb.PCB_SHAPE();sh.SetShape(pcb.SHAPE_T_SEGMENT);sh.SetStart(vec(*a));sh.SetEnd(vec(*z));sh.SetLayer(pcb.Edge_Cuts);sh.SetWidth(pcb.FromMM(.05));b.Add(sh)
    for a,m,z in [((124,100),(124.707107,100.292893),(125,101)),((125,124),(124.707107,124.707107),(124,125)),
                  ((101,125),(100.292893,124.707107),(100,124)),((100,101),(100.292893,100.292893),(101,100))]:
        sh=pcb.PCB_SHAPE();sh.SetShape(pcb.SHAPE_T_ARC);sh.SetArcGeometry(vec(*a),vec(*m),vec(*z));sh.SetLayer(pcb.Edge_Cuts);sh.SetWidth(pcb.FromMM(.05));b.Add(sh)
    for txt,x,y,layer in (BOARD_TEXT or [("SL25 REV A",112.5,108.0,pcb.B_SilkS),("USB STATUS",112.5,110,pcb.B_SilkS),
                          ("BOOT",120.7,116,pcb.B_SilkS),("5V",103,123,pcb.B_SilkS),("GND",105.5,123,pcb.B_SilkS)]):
        t=pcb.PCB_TEXT(b);t.SetText(txt);t.SetPosition(vec(x,y));t.SetTextSize(vec(.8,.8));t.SetTextThickness(pcb.FromMM(.12));t.SetLayer(layer)
        if layer==pcb.B_SilkS:t.SetMirrored(True)
        b.Add(t)
    (OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "SL25") (type "KiCad") (uri "${KIPRJMOD}/SL25.pretty") (options "") (descr "Vendored KiCad footprints")))',encoding="utf-8")
    pcb.SaveBoard(str(OUT/f"{NAME}.kicad_pcb"),b)
    return b,fps,nets


def metadata():
    project={"meta":{"filename":f"{NAME}.kicad_pro","version":1},
             "board":{"design_settings":{"rules":{"min_clearance":.15,"min_track_width":.15,
                        "min_via_diameter":.6,"min_through_hole_diameter":.3,"min_hole_to_hole":.25,"min_hole_clearance":.18,
                        "min_copper_edge_clearance":.3,"min_silk_clearance":.1,"min_silk_text_height":.6,"min_silk_text_thickness":.1}}},
             "net_settings":{"classes":[{"name":"Default","clearance":.15,"track_width":.2,"via_diameter":.6,"via_drill":.3,
                        "diff_pair_width":.2,"diff_pair_gap":.2,"diff_pair_via_gap":.25,"wire_width":6,"bus_width":12}],"version":4}}
    (OUT/f"{NAME}.kicad_pro").write_text(json.dumps(project,indent=2),encoding="utf-8")
    with (OUT/"BOM.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["Reference","Value","MPN_or_specification","Footprint","Side","Quantity","Notes"])
        for p in parts:w.writerow([p["ref"],p["value"],p["mpn"],p["fp"],"Bottom" if p["back"] else "Top",1,p["note"]])
    (OUT/"design_manifest.json").write_text(json.dumps(parts,indent=2),encoding="utf-8")


if __name__=="__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    metadata();schematic();b,fps,nets=make_board()
    print(f"Created {len(parts)} footprints, {len(nets)} nets in {OUT}")
    for ref in ["U2","JP1"]:
        print(ref,[(p.GetNumber(),tuple(pcb.ToMM(p.GetPosition()))) for p in fps[ref].Pads()])
