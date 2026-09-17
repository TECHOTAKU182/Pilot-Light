"""Finalize copper, local 3D assets, fabrication exports, and KiCad checks."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import pcbnew as pcb

ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent/"sl25"
FILE=ROOT/"sl25.kicad_pcb"
CLI=Path(pcb.__file__).parents[2]/"kicad-cli.exe"
MODELS=Path(os.environ.get("KICAD_3DMODEL_DIR","E:/Kicard/share/kicad/3dmodels"))


def vec(x,y):return pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))


def run(*args):
    result=subprocess.run([str(CLI),*map(str,args)],capture_output=True)
    log=result.stdout.decode("utf-8",errors="replace")+result.stderr.decode("utf-8",errors="replace")
    with (ROOT/"checks"/"export.log").open("a",encoding="utf-8") as f:f.write(" ".join(map(str,args))+"\n"+log+"\n")
    print(" ".join(map(str,args[:3])),"exit",result.returncode,flush=True)
    if result.returncode:raise RuntimeError(log)


if __name__=="__main__":
    for d in ["models","checks","preview","fabrication","mechanical"]:(ROOT/d).mkdir(exist_ok=True)
    (ROOT/"checks"/"export.log").write_text("",encoding="utf-8")
    b=pcb.LoadBoard(str(FILE))
    project_path=ROOT/"sl25.kicad_pro"
    project=json.loads(project_path.read_text(encoding="utf-8"))
    # The manufacturer's USB4105 pattern has 0.1944 mm pad-to-locating-hole spacing.
    project["board"]["design_settings"]["rules"]["min_hole_clearance"]=.18
    project_path.write_text(json.dumps(project,indent=2),encoding="utf-8")
    b.GetDesignSettings().m_HoleClearance=pcb.FromMM(.18)
    fps={f.GetReference():f for f in b.GetFootprints()}
    for ref in ["TP1","TP2"]:fps[ref].Reference().SetVisible(False)
    for pad in fps["J1"].Pads():
        if pad.GetNumber()=="SH":pad.SetLocalZoneConnection(pcb.ZONE_CONNECTION_FULL)
    if b.GetTitleBlock().GetRevision() != "B":
        fps["D1"].Reference().SetPosition(vec(118.6,105.3))
        for ref in ["TP3","TP4","TP5","TP6"]:
            f=fps[ref];x,y=pcb.ToMM(f.GetPosition());f.Reference().SetPosition(vec(x,105.3))
    else:
        for ref in ("TP4", "TP5"):
            f=fps[ref];x,y=pcb.ToMM(f.GetPosition());f.Reference().SetPosition(vec(x,100.6))
    # Copy the actual KiCad STEP models so the project opens without machine-specific paths.
    assets=[]
    for fp in b.GetFootprints():
        models=fp.Models()
        for index,model in enumerate(models):
            raw=model.m_Filename
            if raw.startswith("${KIPRJMOD}/models/"):continue
            relative=raw.split("}/",1)[-1]
            source=MODELS/relative
            if not source.is_file():raise FileNotFoundError(source)
            dest=ROOT/"models"/source.name
            shutil.copy2(source,dest)
            model.m_Filename="${KIPRJMOD}/models/"+source.name
            models[index]=model
            assets.append(source.name)
            local=ROOT/"SL25.pretty"/(str(fp.GetFPID().GetLibItemName())+".kicad_mod")
            local.write_text(local.read_text(encoding="utf-8").replace(raw,model.m_Filename),encoding="utf-8")
    # Both layers reference GND; retain explicit ground tracks as connectivity fallback.
    if not list(b.Zones()):
        net=b.FindNet("/GND")
        for layer in [pcb.F_Cu,pcb.B_Cu]:
            z=pcb.ZONE(b);z.SetLayer(layer);z.SetNet(net);z.SetLocalClearance(pcb.FromMM(.2))
            z.SetPadConnection(pcb.ZONE_CONNECTION_THERMAL);z.SetThermalReliefGap(pcb.FromMM(.25));z.SetThermalReliefSpokeWidth(pcb.FromMM(.25))
            z.SetMinThickness(pcb.FromMM(.2));z.SetIslandRemovalMode(pcb.ISLAND_REMOVAL_MODE_ALWAYS)
            outline=z.Outline();outline.NewOutline()
            for x,y in [(100.4,100.4),(124.6,100.4),(124.6,124.6),(100.4,124.6)]:outline.Append(int(pcb.FromMM(x)),int(pcb.FromMM(y)))
            b.Add(z)
    b.BuildConnectivity();pcb.ZONE_FILLER(b).Fill(b.Zones())
    pcb.SaveBoard(str(FILE),b)
    run("sch","erc",ROOT/"sl25.kicad_sch","--exit-code-violations","-o",ROOT/"checks"/"erc.rpt")
    run("pcb","drc",FILE,"--schematic-parity","--exit-code-violations","-o",ROOT/"checks"/"drc.rpt")
    run("pcb","export","gerbers",FILE,"-o",str(ROOT/"fabrication")+"/","-l","F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts")
    run("pcb","export","drill",FILE,"-o",str(ROOT/"fabrication")+"/","--format","excellon","--excellon-units","mm","--excellon-separate-th","--generate-map","--map-format","svg")
    run("pcb","export","pos",FILE,"-o",ROOT/"fabrication"/"positions.csv","--format","csv","--units","mm")
    run("pcb","export","step",FILE,"-o",ROOT/"mechanical"/"sl25.step","--force","--user-origin","100x100mm")
    run("sch","export","svg",ROOT/"sl25.kicad_sch","-o",str(ROOT/"preview")+"/")
    for side,rotate in [("top",None),("bottom",None),("top","35,0,30")]:
        name="board-isometric" if rotate else "board-"+side
        args=["pcb","render",FILE,"-o",ROOT/"preview"/(name+".png"),"--side",side,"--width","1400","--height","1400","--background","opaque","--zoom","0.65" if rotate else "0.8"]
        if rotate:args.extend(["--rotate",rotate])
        run(*args)
    (ROOT/"checks"/"model_assets.json").write_text(json.dumps(sorted(p.name for p in (ROOT/"models").glob("*.step")),indent=2),encoding="utf-8")
    print("Finished fabrication exports and checks",flush=True)
