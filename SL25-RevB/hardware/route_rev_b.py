"""Route Rev B after deterministic USB-C A/B pair breakouts."""
from pathlib import Path
import pcbnew as pcb
from route_board import Router

root = Path(__file__).resolve().parent / "sl25_rev_b"
file = root / "sl25.kicad_pcb"
board = pcb.LoadBoard(str(file))
if list(board.GetTracks()):
    raise RuntimeError("Regenerate Rev B before routing.")
r = Router(board)
dp = board.FindNet("/USB_DP").GetNetCode()
dm = board.FindNet("/USB_DM").GetNetCode()


def path(net, points, layer):
    for a, b in zip(points, points[1:]):
        r.track(net, a, b, layer)


# The two USB-C data pairs interleave on the connector pad row. Join D+ below
# that row and D- above it, then bring both to the ESD protector.
path(dp, [(111.75, 117.47), (111.75, 118.55), (112.75, 118.55), (112.75, 117.47)], 1)
r.add_via(dp, (112.25, 118.55))
path(dp, [(112.25, 118.55), (111, 117.30), (111, 116.4)], 0)
r.add_via(dp, (111, 116.4))
path(dp, [(111, 116.4), (111.55, 115.85), (111.55, 115.2375)], 1)
path(dm, [(112.25, 117.47), (112.25, 116.55), (113.25, 116.55), (113.25, 117.47)], 1)
path(dm, [(113.25, 116.55), (113.45, 116.35), (113.45, 115.2375)], 1)
for net in (dp, dm):
    r.pads[net] = [(pad, layers) for pad, layers in r.pads[net]
                   if pad.GetParentFootprint().GetReference() != "J1"]
order = sorted(r.pads, key=lambda n: (
    0 if n in (dp, dm) else 1 if board.FindNet(n).GetNetname() == "/V33"
    else 3 if board.FindNet(n).GetNetname() == "/GND" else 2,
    -len(r.pads[n])))
failed = []
for net in order:
    ok = r.route(net)
    print(board.FindNet(net).GetNetname(), "OK" if ok else "FAILED", flush=True)
    if not ok:
        failed.append(board.FindNet(net).GetNetname())
pcb.SaveBoard(str(file), board)
print("Tracks/vias:", len(list(board.GetTracks())), "Unrouted:", failed, flush=True)
if failed:
    raise SystemExit(1)
