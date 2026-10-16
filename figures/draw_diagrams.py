"""Vector drawing primitives; copied into each independent project generator."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)

def checking_pipeline(out):
    d=Drawing((-1.35,-3.15,8.3,.7))
    d.box('query',0,0,2.2,.75,'finite query')
    d.box('producer',3.15,0,2.4,.85,'certificate\nproducer',dashed=True)
    d.box('certificate',6.7,0,2.8,.85,'JSON certificate\nfrontiers + witness')
    d.box('baselines',0,-2.05,2.2,.85,'dense checker\ntrace oracle')
    d.box('result',3.15,-2.05,3.2,.85,'exact bounded result\nor rejection/unknown')
    d.box('checker',6.7,-2.05,2.4,.85,'independent\nchecker')
    d.edge('query','producer','e','w')
    d.edge('producer','certificate','e','w')
    d.edge('certificate','checker')
    d.edge('checker','result','w','e')
    d.edge('query','baselines')
    d.edge('baselines','result','e','w',dashed=True)
    d.arrow((.5,-.375),(6.2,-1.625),via=((.5,-1.05),(6.2,-1.05)))
    d.text(0,-2.78,'evaluation only',size=8)
    d.text(6.7,-2.78,'trusted for acceptance',size=8)
    d.save(out,'checking-pipeline')


def gas_example(out):
    d=Drawing((-.7,-2.15,6.65,1.65))
    d.box('s',0,0,.7,.7,'$s$',shape='circle')
    d.box('a',3,0,.7,.7,'$a$',shape='circle')
    d.box('z',6,0,.7,.7,'$z$',shape='circle')
    d.ax.add_patch(Circle((6,0),.29,fill=False,edgecolor='black',linewidth=.55,zorder=3))
    for sign,label in [(1,'$c=0,\\ d=1$'),(-1,'$c=1,\\ d=0$')]:
        d.ax.add_patch(FancyArrowPatch((.27,sign*.22),(2.73,sign*.22),
            connectionstyle='arc3,rad='+str(-sign*.32),arrowstyle='-|>',
            mutation_scale=7.5,linewidth=.55,color='black'))
        d.text(1.5,sign*.72,label)
    d.edge('a','z','e','w')
    d.text(4.5,.28,'$c=0,\\ d=1$')
    d.arrow((0,-.35),(6,-.35),via=((0,-1.55),(6,-1.55)))
    d.text(3,-1.86,'$c=9,\\ d=0$')
    d.text(3,1.23,'$G=1,\\ H=2$  (guards true; register unchanged)')
    # The zero-cost two-step path consumes two gas units and is infeasible.
    outcomes=[(2,0),(1,1),(0,9)]
    assert min(cost for gas,cost in outcomes if gas<=0)==9
    assert min(cost for gas,cost in outcomes if gas<=1)==1
    d.save(out,'gas-example')


def interval_shift(out):
    d=Drawing((-3.0,-.85,5.15,2.7))
    scale=.6
    d.text(-.3,1.5,'Source gas $g$',ha='right')
    d.text(-.3,.5,'Target gas $g-1$',ha='right')
    for left,right,label in [(0,3,'$I_1=[0,2]$'),(3,7,'$I_2=[3,6]$')]:
        d.box(label,scale*(left+right)/2,1.5,scale*(right-left),.64,label)
    for left,right,label in [(1,3,'$J_1+1$'),(3,7,'$J_2+1$')]:
        d.ax.add_patch(Rectangle((scale*left,.18),scale*(right-left),.64,
            fill=False,edgecolor='black',linewidth=.55,hatch='///'))
        artist=d.text(scale*(left+right)/2,.5,label)
        artist.set_bbox({'facecolor':'white','edgecolor':'none','pad':.6})
    for x in (1,3,7): d.line([(scale*x,.02),(scale*x,1.97)],dashed=True)
    d.arrow((0,-.12),(4.55,-.12));d.text(4.7,-.12,'$g$')
    for x in range(7): d.text(scale*(x+.5),-.43,str(x))
    d.text(1.75,2.33,'$G=6,\\ d=1,\\ J_1=[0,1],\\ J_2=[2,5]$')
    source=[set(range(3)),set(range(3,7))]
    target=[{1,2},set(range(3,7))]
    covered=[a&b for a in source for b in target if a&b]
    assert set().union(*covered)==set(range(1,7))
    assert sum(map(len,covered))==6
    d.save(out,'interval-shift')


def generate(out):
    out.mkdir(parents=True,exist_ok=True)
    checking_pipeline(out);interval_shift(out);gas_example(out)


def main():
    import tempfile
    p=argparse.ArgumentParser(description='Direct Python vector diagrams for the finite-summary certificate.')
    p.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--check',action='store_true')
    a=p.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as t:
            x,y=Path(t)/'a',Path(t)/'b';generate(x);generate(y)
            for name in ('checking-pipeline','interval-shift','gas-example'):
                assert (x/(name+'.pdf')).read_bytes()==(y/(name+'.pdf')).read_bytes(),name
        print('Three diagram relations and deterministic fresh generation passed.')
    else: generate(a.output_dir)
if __name__=='__main__':main()
