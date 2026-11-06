"""Small CPU rasterizer for Script TOP; no Pillow, browser, or external assets."""
import numpy as np
import colorsys

PALETTE = [(83,204,194),(252,179,99),(133,156,247),(229,125,165),
           (175,215,110),(103,186,238),(220,158,243),(232,208,115)]
PALETTE=[tuple(int(v*255) for v in colorsys.hsv_to_rgb((i*.61803398875)%1,.48,.91)) for i in range(32)]
GLYPHS = ['111101101101111','010110010010111','111001111100111',
          '111001111001111','101101111001001','111100111001111',
          '111100111101111','111001010010010','111101111101111','111101111001111']


class View:
    def __init__(self, n, seed, width=900, height=556):
        self.w,self.h = width,height
        rng=np.random.default_rng(seed+10000)
        self.layout_pos=rng.uniform([70,70],[width-70,height-100],(n,2))
        self.pos=self.layout_pos.copy()

    def layout(self, sim, pinned=0):
        # Keep an undistorted simulation layout; fisheye is a display transform
        # and must not compound each frame or feed back into the model.
        p=self.layout_pos
        pinned=int(np.clip(pinned,0,len(p)-1))
        center=np.array([self.w/2,(self.h-45)/2],dtype=float)
        p[pinned]=center
        d=p[:,None,:]-p[None,:,:]
        dist=np.maximum(np.sum(d*d,axis=2),120.)
        rep=np.sum(d*(280./dist)[:,:,None],axis=1)
        att=np.sum(-d*(sim.world.a*.008)[:,:,None],axis=1)
        attraction=(center-p)*.018
        delta=np.clip(rep*.14+att+attraction,-3,3)
        delta[pinned]=0
        p+=delta
        p[:]=np.clip(p,[30,30],[self.w-30,self.h-65])
        self.pos=self.fisheye(p,center,pinned)
        self.pos[pinned]=center

    def fisheye(self, positions, center, pinned, strength=1.8):
        """Radially magnify the focus neighborhood while keeping canvas edges fixed."""
        source=np.asarray(positions,dtype=float)
        out=source.copy()
        offset=source-center
        radii=np.linalg.norm(offset,axis=1)
        valid=(radii>1e-9)
        directions=np.zeros_like(offset)
        directions[valid]=offset[valid]/radii[valid,None]
        ux,uy=directions[:,0],directions[:,1]
        xlim=np.where(ux>=0,(self.w-30-center[0])/np.maximum(ux,1e-12),
                      (30-center[0])/np.minimum(ux,-1e-12))
        ylim=np.where(uy>=0,(self.h-65-center[1])/np.maximum(uy,1e-12),
                      (30-center[1])/np.minimum(uy,-1e-12))
        boundary=np.minimum(np.abs(xlim),np.abs(ylim))
        boundary=np.maximum(boundary,1e-9)
        normalized=np.clip(radii/boundary,0.,1.)
        warped=(1.+strength)*normalized/(1.+strength*normalized)
        out[valid]=center+directions[valid]*(warped[valid]*boundary[valid])[:,None]
        out[pinned]=center
        return out

    def image(self, sim, actor, target, mode='network'):
        world=sim.world
        labels=world.detector.labels
        a=np.empty((self.h,self.w,4),dtype=np.uint8)
        a[:]=[12,20,31,255]
        a[::40,:,:3]=[17,28,40]
        a[:,::40,:3]=[17,28,40]
        def dot(x,y,r,color):
            x,y=int(x),int(y)
            x0,x1=max(0,x-r),min(self.w,x+r+1)
            y0,y1=max(0,y-r),min(self.h,y+r+1)
            yy,xx=np.ogrid[y0:y1,x0:x1]
            m=(xx-x)**2+(yy-y)**2<=r*r
            a[y0:y1,x0:x1,:3][m]=color
        def line(p,q,color,width=1):
            num=max(2,int(np.linalg.norm(q-p)))
            xy=np.linspace(p,q,num).astype(int)
            xy[:,0]=np.clip(xy[:,0],0,self.w-1)
            xy[:,1]=np.clip(xy[:,1],0,self.h-1)
            for dx in range(-width+1,width):
                a[xy[:,1],np.clip(xy[:,0]+dx,0,self.w-1),:3]=color
        for i,j in np.argwhere(np.triu(world.a,1)):
            c=int(labels[i])
            same=c>=0 and labels[i]==labels[j]
            color=np.asarray(PALETTE[c%len(PALETTE)] if same else (110,125,145))*(.75 if mode=='network' else .22)
            line(self.pos[i],self.pos[j],color.astype(int))
        if mode=='affinity':
            for j in range(sim.n):
                if j==actor:continue
                v=world.x[actor,j]
                if abs(v)<.04:continue
                color=(np.array((65,218,183) if v>0 else (250,101,117))*(.3+.7*abs(v))).astype(int)
                line(self.pos[actor],self.pos[j],color,1+(abs(v)>.65))
                dot(*(self.pos[actor]*.2+self.pos[j]*.8),3,color)
        if mode=='information':
            for i,j in world.transmissions:
                line(self.pos[i],self.pos[j],(255,196,110),2)
                dot(*(self.pos[i]*.25+self.pos[j]*.75),4,(255,222,169))
        for i,j in world.removed:
            line(self.pos[i],self.pos[j],(248,101,112),2)
        for i,j in world.added:
            line(self.pos[i],self.pos[j],(168,248,176),2)
        for i,(x,y) in enumerate(self.pos):
            color=PALETTE[int(labels[i])%len(PALETTE)] if labels[i]>=0 else (145,157,176)
            if mode=='information' and world.events and world.events[-1]['seen'][i]:dot(x,y,15,(213,140,62))
            if i==actor:dot(x,y,18,(244,209,120))
            if i==target:dot(x,y,17,(244,245,250))
            dot(x,y,13,(15,24,36))
            dot(x,y,11,color if world.a[i].any() else (59,74,94))
            digits=str(i+1)
            ox=int(x)-len(digits)*4
            for n,ch in enumerate(digits):
                for k,pixel in enumerate(GLYPHS[int(ch)]):
                    if pixel=='1':
                        px=ox+n*8+(k%3)*2
                        py=int(y)-5+(k//3)*2
                        a[py:py+2,px:px+2,:3]=[10,19,30] if world.a[i].any() else [210,224,239]
        # Divergence from the no-action counterfactual, with displayed autoscale.
        hist=sim.history[-400:]
        scale=max(.001,max(h['difference'] for h in hist))
        y0=self.h-16
        a[self.h-47:,:,:3]=[15,26,39]
        for k in range(1,len(hist)):
            x1=20+(self.w-40)*(k-1)/max(1,len(hist)-1)
            x2=20+(self.w-40)*k/max(1,len(hist)-1)
            line(np.array([x1,y0-28*hist[k-1]['difference']/scale]),
                 np.array([x2,y0-28*hist[k]['difference']/scale]),(245,192,115),2)
        return a.astype(np.float32)/255.

    def comparison(self,sim,actor,target,changed):
        """Both panels use identical display coordinates; never move model state."""
        from types import SimpleNamespace
        left=View(sim.n,sim.seed,width=450,height=self.h)
        left.pos=self.pos.copy();left.pos[:,0]*=.5
        base=SimpleNamespace(world=sim.base,n=sim.n,history=sim.history)
        first=left.image(base,actor,target)
        second=left.image(sim,actor,target)
        image=np.concatenate([first,second],axis=1)
        image[:,449:451,:3]=(.25,.38,.47)
        for i in changed:
            for offset in (0,450):
                x,y=left.pos[i];x=int(x)+offset;y=int(y)
                yy,xx=np.ogrid[:self.h,:self.w]
                ring=((xx-x)**2+(yy-y)**2>=19**2)&((xx-x)**2+(yy-y)**2<=21**2)
                image[ring,:3]=(.98,.47,.51)
        return image

    def distribution(self,rows,actor):
        """Every person's actual value; rows overlap deliberately across role tags."""
        image=np.ones((self.h,self.w,4),np.float32);image[:,:,:3]=(.047,.078,.122)
        flags=('hub','multi_community_connector','structural_broker','isolated')
        keys=('formation','cut','receptivity','spread')
        for col,key in enumerate(keys):
            left=col*225+24;right=left+185
            for row,flag in enumerate(flags):
                y=65+row*123
                image[y+22:y+23,left:right,:3]=(.3,.38,.46)
                for person in rows:
                    if not person[flag]:continue
                    value=person[key];normalized=(value+1)/2 if key=='cut' else value
                    x=int(left+185*np.clip(normalized,0,1));py=y+(person['person']*17%31)-15
                    r=4 if person['person']==actor+1 else 2
                    image[py-r:py+r+1,x-r:x+r+1,:3]=(.98,.81,.4) if r==4 else np.array(PALETTE[row])/255.
        return image
