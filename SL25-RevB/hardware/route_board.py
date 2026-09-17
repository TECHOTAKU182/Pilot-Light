"""Two-layer grid routing for the fixed SL25 prototype; validate with KiCad DRC."""
import heapq
import math
import sys
from pathlib import Path
import numpy as np
import pcbnew as pcb

ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent/"sl25"
FILE=ROOT/"sl25.kicad_pcb"
STEP=.05
N=501
WIDTH=.20
CLEAR=.15
MARGIN=.045
ORIGIN=100.0
LAYERS=[pcb.F_Cu,pcb.B_Cu]


def vec(x,y):return pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))
def xy(p):return tuple(pcb.ToMM(p))
def grid(x,y):return round((x-ORIGIN)/STEP),round((y-ORIGIN)/STEP)
def mm(x,y):return ORIGIN+x*STEP,ORIGIN+y*STEP


class Router:
    def __init__(self,b):
        self.b=b
        self.trace=np.zeros((2,N,N),dtype=np.int32)
        self.via=np.zeros((2,N,N),dtype=np.int32)
        self.pads={}
        for fp in b.GetFootprints():
            for p in fp.Pads():
                num=p.GetNetCode()
                layers=[i for i,l in enumerate(LAYERS) if p.IsOnLayer(l)]
                # Non-plated mechanical holes are keepouts on both copper layers.
                if p.GetAttribute()==pcb.PAD_ATTRIB_NPTH:layers=[0,1]
                box=p.GetBoundingBox()
                x0,y0=xy(box.GetPosition());sx,sy=xy(box.GetSize())
                for i in layers:
                    clearance=.25 if p.GetAttribute()==pcb.PAD_ATTRIB_NPTH else CLEAR
                    self.rect(self.trace[i],x0,y0,x0+sx,y0+sy,clearance+WIDTH/2+MARGIN,num or -1)
                    self.rect(self.via[i],x0,y0,x0+sx,y0+sy,CLEAR+.3+MARGIN,num or -1)
                if p.GetDrillSize().x:
                    dx,dy=xy(p.GetDrillSize());px,py=xy(p.GetPosition())
                    if round(p.GetOrientationDegrees())%180:dx,dy=dy,dx
                    for i in [0,1]:self.rect(self.via[i],px-dx/2,py-dy/2,px+dx/2,py+dy/2,.15+.25+MARGIN,-1)
                if num and layers:
                    self.pads.setdefault(num,[]).append((p,layers))
        for arr,edge in [(self.trace,.3+WIDTH/2+MARGIN),(self.via,.3+.3+MARGIN)]:
            k=math.ceil(edge/STEP)
            arr[:,:k,:]=-1;arr[:,-k:,:]=-1;arr[:,:,:k]=-1;arr[:,:,-k:]=-1
        self.existing_vias={}

    @staticmethod
    def paint(arr,sl,mask,net):
        a=arr[sl];old=a[mask]
        a[mask]=np.where((old==0)|(old==net),net,-1)

    def rect(self,arr,x0,y0,x1,y1,inflate,net):
        a,b=grid(x0-inflate,y0-inflate);c,d=grid(x1+inflate,y1+inflate)
        a=max(0,a);b=max(0,b);c=min(N-1,c);d=min(N-1,d)
        if c<a or d<b:return
        self.paint(arr,(slice(b,d+1),slice(a,c+1)),np.ones((d-b+1,c-a+1),dtype=bool),net)

    def segment_mask(self,arr,a,b,r,net):
        x0,y0=a;x1,y1=b
        ax,ay=grid(min(x0,x1)-r,min(y0,y1)-r);bx,by=grid(max(x0,x1)+r,max(y0,y1)+r)
        ax=max(ax,0);ay=max(ay,0);bx=min(bx,N-1);by=min(by,N-1)
        xx=ORIGIN+np.arange(ax,bx+1)[None,:]*STEP
        yy=ORIGIN+np.arange(ay,by+1)[:,None]*STEP
        dx=x1-x0;dy=y1-y0
        den=dx*dx+dy*dy
        t=np.clip(((xx-x0)*dx+(yy-y0)*dy)/den,0,1) if den else 0
        mask=(xx-(x0+t*dx))**2+(yy-(y0+t*dy))**2<=r*r
        self.paint(arr,(slice(ay,by+1),slice(ax,bx+1)),mask,net)

    def track(self,net,a,b,layer,width=WIDTH):
        if math.dist(a,b)<.001:return
        t=pcb.PCB_TRACK(self.b);t.SetStart(vec(*a));t.SetEnd(vec(*b));t.SetWidth(pcb.FromMM(width));t.SetLayer(LAYERS[layer]);t.SetNetCode(net);self.b.Add(t)
        self.segment_mask(self.trace[layer],a,b,width/2+WIDTH/2+CLEAR+MARGIN,net)
        self.segment_mask(self.via[layer],a,b,width/2+.3+CLEAR+MARGIN,net)

    def add_via(self,net,point):
        if (net,point) in self.existing_vias:return
        v=pcb.PCB_VIA(self.b);v.SetPosition(vec(*point));v.SetWidth(pcb.FromMM(.6));v.SetDrill(pcb.FromMM(.3));v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(*LAYERS);v.SetNetCode(net);self.b.Add(v)
        for l in [0,1]:
            self.segment_mask(self.trace[l],point,point,.3+WIDTH/2+CLEAR+MARGIN,net)
            self.segment_mask(self.via[l],point,point,.3+.3+CLEAR+MARGIN,net)
            self.segment_mask(self.via[l],point,point,.3+.25+MARGIN,-1)
            x,y=grid(*point);self.via[l,y,x]=net
        self.existing_vias[(net,point)]=True

    def search(self,net,source,targets):
        sp,sl=source;sx,sy=grid(*xy(sp.GetPosition()))
        ends=set()
        for tp,tl in targets:
            tx,ty=grid(*xy(tp.GetPosition()))
            for l in tl:ends.add((l,tx,ty))
        endlist=list(ends)
        def heuristic(x,y):
            return min(max(abs(x-ex),abs(y-ey))+.4142*min(abs(x-ex),abs(y-ey)) for _,ex,ey in endlist)
        opened=[];cost={};prev={}
        for l in sl:
            node=(l,sx,sy);cost[node]=0;heapq.heappush(opened,(heuristic(sx,sy),0,node))
        counter=0
        while opened:
            _,g,node=heapq.heappop(opened)
            if g!=cost.get(node):continue
            if node in ends:
                path=[node]
                while node in prev:node=prev[node];path.append(node)
                return path[::-1]
            l,x,y=node;counter+=1
            if counter>900000:break
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
                nx,ny=x+dx,y+dy
                if not(0<=nx<N and 0<=ny<N):continue
                cell=self.trace[l,ny,nx]
                if cell!=0 and cell!=net:continue
                if dx and dy:
                    if self.trace[l,y,nx] not in (0,net) or self.trace[l,ny,x] not in (0,net):continue
                ng=g+(1.414214 if dx and dy else 1)
                nxt=(l,nx,ny)
                if ng<cost.get(nxt,math.inf):
                    cost[nxt]=ng;prev[nxt]=node;heapq.heappush(opened,(ng+heuristic(nx,ny),ng,nxt))
            if all(self.via[k,y,x] in (0,net) for k in [0,1]) and all(self.trace[k,y,x] in (0,net) for k in [0,1]):
                nxt=(1-l,x,y);ng=g+100
                if ng<cost.get(nxt,math.inf):
                    cost[nxt]=ng;prev[nxt]=node;heapq.heappush(opened,(ng+heuristic(x,y),ng,nxt))
        return None

    def route(self,net):
        pads=self.pads[net]
        connected=[pads[0]];todo=pads[1:]
        while todo:
            source=min(todo,key=lambda s:min(math.dist(xy(s[0].GetPosition()),xy(t[0].GetPosition())) for t in connected))
            if any(math.dist(xy(source[0].GetPosition()),xy(t[0].GetPosition()))<.001 and set(source[1])&set(t[1]) for t in connected):
                connected.append(source);todo.remove(source);continue
            # The closest already-connected pad keeps local branches short.
            target=min(connected,key=lambda t:math.dist(xy(source[0].GetPosition()),xy(t[0].GetPosition())))
            path=self.search(net,source,[target])
            if path is None:
                print("UNROUTED",self.b.FindNet(net).GetNetname(),source[0].GetParentFootprint().GetReference(),source[0].GetNumber(),flush=True)
                return False
            l,x,y=path[0];start=mm(x,y)
            self.track(net,xy(source[0].GetPosition()),start,l)
            run=start;last=path[0];direction=None
            for cur in path[1:]:
                cl,cx,cy=cur;pl,px,py=last
                if cl!=pl:
                    self.track(net,run,mm(px,py),pl);self.add_via(net,mm(px,py));run=mm(cx,cy);direction=None
                else:
                    d=(cx-px,cy-py)
                    if direction is not None and d!=direction:
                        self.track(net,run,mm(px,py),pl);run=mm(px,py)
                    direction=d
                last=cur
            l,x,y=last;self.track(net,run,mm(x,y),l)
            self.track(net,mm(x,y),xy(target[0].GetPosition()),l)
            connected.append(source);todo.remove(source)
        return True


if __name__=="__main__":
    b=pcb.LoadBoard(str(FILE))
    if len(list(b.GetTracks())):raise RuntimeError("Regenerate the placement before routing.")
    r=Router(b)
    order=sorted(r.pads,key=lambda n:(0 if b.FindNet(n).GetNetname().lstrip('/') in ["USB_DP","USB_DM"] else 1 if b.FindNet(n).GetNetname().lstrip('/')=="V33" else 3 if b.FindNet(n).GetNetname().lstrip('/')=="GND" else 2,-len(r.pads[n])))
    failed=[]
    for net in order:
        ok=r.route(net)
        print(b.FindNet(net).GetNetname(),"OK" if ok else "FAILED",flush=True)
        if not ok:failed.append(b.FindNet(net).GetNetname())
    pcb.SaveBoard(str(FILE),b)
    print("Tracks/vias:",len(list(b.GetTracks())),"Unrouted nets:",failed,flush=True)
