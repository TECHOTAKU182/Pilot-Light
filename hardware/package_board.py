"""Check critical hardware invariants and package the already-verified design."""
from pathlib import Path
import hashlib
import json
import math
import zipfile
import pcbnew as pcb

ROOT=Path(__file__).resolve().parent
DESIGN=ROOT/"sl25"
b=pcb.LoadBoard(str(DESIGN/"sl25.kicad_pcb"))
fps={f.GetReference():f for f in b.GetFootprints()}


def net(ref,pin):
    values={p.GetNetname().lstrip('/') for p in fps[ref].Pads() if p.GetNumber()==str(pin)}
    assert len(values)==1,(ref,pin,values)
    return values.pop()


# Pin assignments below are the externally reviewed datasheet expectations.
for pin,expected in {3:"PWM_RED",11:"PWM_GREEN",9:"GPIO_BLUE",12:"USB_DP",13:"USB_DM",14:"GND",15:"+5V",16:"V33"}.items():
    assert net("U1",pin)==expected
for pin,expected in {1:"LED_RED",2:"GND",3:"LED_BLUE",4:"LED_GREEN"}.items():
    assert net("D1",pin)==expected
for pin,expected in {"A6":"USB_DP","B6":"USB_DP","A7":"USB_DM","B7":"USB_DM","A5":"CC1","B5":"CC2","SH":"GND"}.items():
    assert net("J1",pin)==expected
assert net("R1",1)=="CC1" and net("R2",1)=="CC2"
assert net("R1",2)==net("R2",2)=="GND"
assert net("C2",1)=="V33" and net("C2",2)=="GND"
assert net("R6",1)=="+5V" and net("R6",2)==net("JP1",1)=="BOOT_PULL"
assert net("JP1",2)=="USB_DP"
for r in ["R3","R4","R5"]:assert fps[r].GetValue()=="1k"
assert b.GetCopperLayerCount()==2
assert abs(pcb.ToMM(b.GetDesignSettings().GetBoardThickness())-1.6)<.001
for ref,expected in [("H1",(102.7,102.7)),("H2",(122.3,102.7))]:
    assert math.dist(tuple(pcb.ToMM(fps[ref].GetPosition())),expected)<.001
    assert abs(pcb.ToMM(next(iter(fps[ref].Pads())).GetDrillSize().x)-2.2)<.001
for fp in b.GetFootprints():
    for m in fp.Models():
        assert m.m_Filename.startswith("${KIPRJMOD}/models/")
        assert (DESIGN/m.m_Filename.replace("${KIPRJMOD}/","")).is_file()
report=(DESIGN/"checks/drc.rpt").read_text(encoding="utf-8")
for text in ["Found 0 DRC violations","Found 0 unconnected pads","Found 0 Footprint errors"]:assert text in report
erc=(DESIGN/"checks/erc.rpt").read_text(encoding="utf-8")
assert "Errors 0" in erc and "Warnings 0" in erc
step=(DESIGN/"mechanical/sl25.step").read_text(encoding="utf-8")
for expected in ["SOIC-16_3.9x9.9mm_P1.27mm","LED_D5.0mm-4_RGB_Wide_Pins","USB_C_Receptacle_GCT_USB4105","SOT-23-6"]:assert expected in step
for file in ["sl25-PTH.drl","sl25-NPTH.drl","sl25-F_Cu.gtl","sl25-B_Cu.gbl","sl25-Edge_Cuts.gm1"]:
    assert (DESIGN/"fabrication"/file).stat().st_size>100

result={"tool":"KiCad 10.0.6","revision":"A","status":"design_checks_passed_not_bench_tested",
        "footprints":len(fps),"copper_layers":2,"board_mm":[25,25,1.6],
        "erc_errors":0,"erc_warnings":0,"drc_violations":0,"unconnected_pads":0,"schematic_parity_issues":0,
        "critical_pinmap_checks":"passed","local_model_paths":"passed","step_contains_component_models":"passed",
        "physical_validation":"not performed"}
(DESIGN/"checks/verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")

files=[p for p in DESIGN.rglob("*") if p.is_file() and not p.name.endswith((".lck",".kicad_prl"))]
hashes={str(p.relative_to(DESIGN)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.name!="SHA256SUMS.json"}
(DESIGN/"SHA256SUMS.json").write_text(json.dumps(hashes,indent=2),encoding="utf-8")
with zipfile.ZipFile(ROOT/"SL25-RevA-project.zip","w",zipfile.ZIP_DEFLATED) as z:
    for p in DESIGN.rglob("*"):
        if p.is_file() and not p.name.endswith((".lck",".kicad_prl")):
            z.write(p,"SL25-RevA/hardware/sl25/"+str(p.relative_to(DESIGN)))
    for p in ROOT.glob("*.py"):z.write(p,"SL25-RevA/hardware/"+p.name)
    for p in (ROOT/"reference").glob("*.pdf"):z.write(p,"SL25-RevA/hardware/reference/"+p.name)
with zipfile.ZipFile(ROOT/"SL25-RevA-gerbers.zip","w",zipfile.ZIP_DEFLATED) as z:
    for p in (DESIGN/"fabrication").iterdir():
        if p.suffix in [".gtl",".gbl",".gts",".gbs",".gto",".gbo",".gtp",".gbp",".gm1",".drl",".gbrjob"]:z.write(p,p.name)
for name in ["SL25-RevA-project.zip","SL25-RevA-gerbers.zip"]:
    with zipfile.ZipFile(ROOT/name) as z:assert z.testzip() is None
print(json.dumps(result,indent=2))
print("Packages:",ROOT/"SL25-RevA-project.zip",ROOT/"SL25-RevA-gerbers.zip")
