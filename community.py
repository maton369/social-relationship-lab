"""CPM/Leiden measurement and temporal identity, separate from social dynamics."""
from collections import deque
import math
import numpy as np
import igraph as ig
import leidenalg as la


def canonical(membership):
    groups={}
    for i,c in enumerate(membership):groups.setdefault(int(c),[]).append(i)
    return tuple(sorted((tuple(v) for v in groups.values()),key=lambda v:v[0]))


def quality(a,groups,gamma):
    return float(sum(a[np.ix_(g,g)].sum()/2-gamma*len(g)*(len(g)-1)/2 for g in groups))


def partition_vi(a,b):
    """Variation of information in bits; invariant to label permutations."""
    n=len(a)
    if not n:return 0.
    aa=[set(np.flatnonzero(a==v)) for v in set(a)]
    bb=[set(np.flatnonzero(b==v)) for v in set(b)]
    ha=-sum(len(s)/n*math.log2(len(s)/n) for s in aa)
    hb=-sum(len(s)/n*math.log2(len(s)/n) for s in bb)
    mi=0.
    for s in aa:
        for t in bb:
            k=len(s&t)
            if k:mi+=k/n*math.log2(k*n/(len(s)*len(t)))
    return max(0.,ha+hb-2*mi)


def assignment(scores):
    """Maximum-weight one-to-one assignment (padded Hungarian algorithm)."""
    rows,cols=scores.shape
    n=max(rows,cols)
    if not n:return []
    cost=np.zeros((n,n));cost[:rows,:cols]=-scores
    u=np.zeros(n+1);v=np.zeros(n+1);p=np.zeros(n+1,dtype=int);way=np.zeros(n+1,dtype=int)
    for i in range(1,n+1):
        p[0]=i;j0=0;minimum=np.full(n+1,np.inf);used=np.zeros(n+1,bool)
        while True:
            used[j0]=True;i0=p[j0];delta=np.inf;j1=0
            for j in range(1,n+1):
                if used[j]:continue
                cur=cost[i0-1,j-1]-u[i0]-v[j]
                if cur<minimum[j]:minimum[j]=cur;way[j]=j0
                if minimum[j]<delta:delta=minimum[j];j1=j
            for j in range(n+1):
                if used[j]:u[p[j]]+=delta;v[j]-=delta
                else:minimum[j]-=delta
            j0=j1
            if p[j0]==0:break
        while True:
            j1=way[j0];p[j0]=p[j1];j0=j1
            if j0==0:break
    return [(int(p[j]-1),j-1) for j in range(1,n+1) if p[j]<=rows and j<=cols and p[j]>0]


class Detector:
    def __init__(self,gamma=.25,seed=23,starts=6):
        self.gamma=float(gamma);self.seed=int(seed);self.starts=starts
        self.cache={};self.previous=();self.ids={};self.next_id=1
        self.labels=None;self.raw=None;self.groups=();self.score=0.;self.ambiguous=None
        self.events=[];self.pending=[];self.signature=None;self.last_step=0

    def detect(self,a,step=0,track_events=True):
        key=(a.tobytes(),self.gamma)
        if key not in self.cache:
            edges=[tuple(map(int,e)) for e in np.argwhere(np.triu(a,1))]
            graph=ig.Graph(n=len(a),edges=edges,directed=False)
            results={}
            for r in range(self.starts):
                part=la.find_partition(graph,la.CPMVertexPartition,
                    resolution_parameter=self.gamma,n_iterations=-1,seed=self.seed+r)
                groups=canonical(part.membership)
                results[groups]=quality(a,groups,self.gamma)
            best=max(results.values())
            options=sorted(g for g,q in results.items() if abs(q-best)<1e-9)
            self.cache[key]=(best,options)
        self.score,options=self.cache[key]
        # Only an exactly tied objective may inherit the previous partition.
        previous=canonical(self.raw) if self.raw is not None else None
        if previous is not None and quality(a,previous,self.gamma)>self.score+1e-9:
            self.score=quality(a,previous,self.gamma);options=[previous]
        if previous is not None and abs(quality(a,previous,self.gamma)-self.score)<1e-9:
            chosen=previous
        else:chosen=options[0]
        raw=np.empty(len(a),int)
        for j,g in enumerate(chosen):raw[list(g)]=j
        ambiguous=np.zeros(len(a),bool)
        chosen_pairs=raw[:,None]==raw[None,:]
        for option in options:
            labels=np.empty(len(a),int)
            for j,g in enumerate(option):labels[list(g)]=j
            ambiguous |= np.any(chosen_pairs!=(labels[:,None]==labels[None,:]),axis=1)
        self.ambiguous=ambiguous;self.raw=raw;self.options=list(options)
        groups=tuple(g for g in chosen if len(g)>=2)
        if groups!=self.groups:
            old=dict(self.ids);newsets=[set(g) for g in groups];oldkeys=sorted(old)
            scores=np.zeros((len(oldkeys),len(newsets)))
            for i,c in enumerate(oldkeys):
                for j,g in enumerate(newsets):scores[i,j]=len(old[c]&g)/len(old[c]|g)
            ids={};used=set()
            for i,j in assignment(scores):
                if scores[i,j]>=.25:ids[oldkeys[i]]=newsets[j];used.add(j)
            for j,g in enumerate(newsets):
                if j not in used:ids[self.next_id]=g;self.next_id+=1
            self.ids=ids
            candidates=[]
            for c,g in old.items():
                overlap=[d for d,h in ids.items() if len(g&h)>=2]
                if len(overlap)>=2:candidates.append({'kind':'split','from':[c],'to':overlap})
                elif not any(g&h for h in ids.values()):candidates.append({'kind':'disappear','from':[c],'to':[]})
            for d,h in ids.items():
                overlap=[c for c,g in old.items() if len(g&h)>=2]
                if len(overlap)>=2:candidates.append({'kind':'merge','from':overlap,'to':[d]})
                elif old and not any(g&h for g in old.values()):candidates.append({'kind':'appear','from':[],'to':[d]})
            self.pending=[dict(e,step=step,partition=groups) for e in candidates] if track_events else []
            self.groups=groups
        for e in list(self.pending):
            if step-e['step']>=3:
                self.events.append({k:v for k,v in e.items() if k!='partition'}|{'confirmed_at':step})
                self.pending.remove(e)
        self.labels=np.full(len(a),-1,int)
        for c,g in self.ids.items():self.labels[list(g)]=c
        self.last_step=step
        return self.labels


ANALYSIS_VERSION='2.1'
ROLE_DEFAULTS=dict(community_min=3,hub_min_size=4,hub_degree=3,hub_ratio=.60,high_liking=.50)
BASE_LABELS={'community_member':'コミュニティ所属者','dyad':'二者関係のみ',
             'unassigned_connected':'未所属の接続者','isolated':'孤立者'}


def components(a,removed=-1):
    labels=np.full(len(a),-1,int);next_id=0
    for start in range(len(a)):
        if start==removed or labels[start]>=0:continue
        labels[start]=next_id;todo=[start]
        while todo:
            i=todo.pop()
            for j in np.flatnonzero(a[i]):
                if j!=removed and labels[j]<0:labels[j]=next_id;todo.append(int(j))
        next_id+=1
    return labels


def structural_metrics(a,x,raw,rules):
    """Read-only analysis. Raw CPM blocks retain dyads; primary groups use min size."""
    n=len(a);parts=canonical(raw);sizes={int(raw[g[0]]):len(g) for g in parts}
    major={int(raw[g[0]]):set(g) for g in parts if len(g)>=rules['community_min']}
    labels=np.array([int(c) if int(c) in major else -1 for c in raw])
    connected=components(a);brokers=np.zeros(n,int)
    pairmask=np.triu((labels[:,None]!=labels[None,:]) & (labels[:,None]>=0) &
        (labels[None,:]>=0) & (connected[:,None]==connected[None,:]),1)
    for i in range(n):
        after=components(a,i)
        eligible=pairmask.copy();eligible[i,:]=False;eligible[:,i]=False
        brokers[i]=int(np.count_nonzero(eligible & (after[:,None]!=after[None,:])))
    rows=[]
    for i in range(n):
        c=int(labels[i]);members=major.get(c,set());inside=sum(bool(a[i,j]) for j in members)
        deg=int(a[i].sum());ratio=inside/(len(members)-1) if members else None
        counts={k:int(a[i,list(g)].sum()) for k,g in major.items()}
        kin=np.array([int(a[j,list(members)].sum()) for j in members],float)
        median=float(np.median(kin)) if len(kin) else None
        others=sorted(members-{i});neighbors=np.flatnonzero(a[i]);mask=np.arange(n)!=i
        average=lambda values:float(np.mean(values)) if len(values) else None
        incoming=average(x[others,i]);outgoing=average(x[i,others])
        hub=bool(members and len(members)>=rules['hub_min_size'] and inside>=rules['hub_degree'] and ratio>=rules['hub_ratio'] and inside>median)
        status='isolated' if deg==0 else 'community_member' if members else 'dyad' if sizes[int(raw[i])]==2 else 'unassigned_connected'
        rows.append(dict(base_status=status,degree=deg,community_size=len(members),
            internal_degree=inside,internal_ratio=ratio,external_degree=deg-inside,
            communities_contacted=sum(v>0 for v in counts.values()),community_connections=counts,
            brokerage_disconnected_pairs=int(brokers[i]),hub=hub,internal_hub=hub,
            high_liking=bool(incoming is not None and incoming>=rules['high_liking']),
            multi_community_connector=sum(v>0 for v in counts.values())>=2,
            structural_broker=bool(brokers[i]>0),internal_peripheral=bool(members and inside<median),
            isolated=deg==0,internal_incoming_mean=incoming,internal_outgoing_mean=outgoing,
            incoming_mean=float(x[mask,i].mean()),outgoing_mean=float(x[i,mask].mean()),
            neighbor_incoming_mean=average(x[neighbors,i]),neighbor_outgoing_mean=average(x[i,neighbors]),
            internal_z=float((inside-kin.mean())/kin.std()) if len(kin) and kin.std()>1e-9 else None))
    return rows


def roles(a,x,detector,traits,initial_a=None,initial_roles=None,formed=None,lost=None,received=None,moves=None,rules=None):
    settings=ROLE_DEFAULTS|dict(rules or {})
    rows=structural_metrics(a,x,detector.raw,settings);n=len(a)
    graph=ig.Graph(n=n,edges=[tuple(map(int,e)) for e in np.argwhere(np.triu(a,1))])
    between=np.asarray(graph.betweenness(directed=False))*(2./((n-1)*(n-2)) if n>2 else 0.)
    flags=('base_status','hub','high_liking','multi_community_connector','structural_broker','internal_peripheral')
    uncertain=np.zeros(n,bool)
    for option in getattr(detector,'options',[]):
        raw=np.empty(n,int)
        for c,g in enumerate(option):raw[list(g)]=c
        if np.array_equal(raw,detector.raw):continue
        other=structural_metrics(a,x,raw,settings)
        for i in range(n):uncertain[i]|=any(rows[i][k]!=other[i][k] for k in flags)
    for i,row in enumerate(rows):
        block=int(detector.labels[i]);members=detector.ids.get(block,set())
        primary=block if len(members)>=settings['community_min'] else None
        counts={str(c):int(a[i,list(g)].sum()) for c,g in detector.ids.items() if len(g)>=settings['community_min']}
        row.update(person=i+1,community=primary,partition_id=block if block>=0 else None,
            dyad_id=block if len(members)==2 else None,partition_size=len(members) or 1,
            community_connections=counts,external_communities=[int(c) for c,k in counts.items() if k and int(c)!=primary],
            betweenness=float(between[i]),ambiguous=bool(detector.ambiguous[i]),role_uncertain=bool(uncertain[i]),
            external_fraction=row['external_degree']/row['degree'] if row['degree'] else 0.,
            incoming_sd=float(x[np.arange(n)!=i,i].std()),outgoing_sd=float(x[i,np.arange(n)!=i].std()),
            formation=float(traits['form'][i]),cut=float(traits['cut'][i]),receptivity=float(traits['receive'][i]),spread=float(traits['spread'][i]),
            initial_degree=int(initial_a[i].sum()) if initial_a is not None else row['degree'],
            formed=int(formed[i]) if formed is not None else 0,lost=int(lost[i]) if lost is not None else 0,
            received_events=int(received[i]) if received is not None else 0,membership_changes=int(moves[i]) if moves is not None else 0)
        row['bridge']=row['multi_community_connector'] # compatibility; UI uses explicit names
        tags=[label for key,label in [('internal_hub','内部ハブ'),('high_liking','高好感度'),
            ('multi_community_connector','横断的接続者'),('structural_broker','構造的橋渡し役'),('internal_peripheral','内部周辺者')] if row[key]]
        if row['role_uncertain']:tags.append('役割判定が不安定')
        elif row['ambiguous']:tags.append('所属曖昧')
        row['role_tags']=tags;row['roles']=[BASE_LABELS[row['base_status']]]+tags
        if initial_roles is not None:
            initial=initial_roles[i]
            row['initial_roles']=initial['roles'];row['initial_base_status']=initial['base_status']
            row['initial_metrics']={k:initial[k] for k in ('degree','internal_degree','internal_ratio','incoming_mean','outgoing_mean','community','brokerage_disconnected_pairs')}
            row['initial_attributes']={k:initial[k] for k in ('formation','cut','receptivity','spread')}
            was=initial['isolated'];now=row['isolated']
            row['isolation_transition']='孤立継続' if was and now else '関係獲得' if was else '孤立化' if now else '関係維持・再編'
    return rows


def community_rows(a,detector,rows,rules=None):
    settings=ROLE_DEFAULTS|dict(rules or {});result=[]
    for c,g in detector.ids.items():
        members=sorted(g);m=int(a[np.ix_(members,members)].sum()//2);primary=len(g)>=settings['community_min']
        external=[dict(person=i+1,ties=int(a[i,members].sum()),source_community=rows[i]['community'],base_status=rows[i]['base_status']) for i in range(len(a)) if i not in g and a[i,members].any()]
        external.sort(key=lambda v:(-v['ties'],v['person']))
        result.append(dict(community_id=c,kind='community' if primary else 'dyad' if len(g)==2 else 'small_group',members=[i+1 for i in members],size=len(g),internal_ties=m,density=2*m/(len(g)*(len(g)-1)),
            internal_hubs=[i+1 for i in sorted(members,key=lambda i:(-rows[i]['internal_degree'],i)) if rows[i]['hub']],
            structural_brokers=[i+1 for i in sorted(members,key=lambda i:(-rows[i]['brokerage_disconnected_pairs'],i)) if rows[i]['structural_broker']],
            external_members=[v for v in external if v['source_community'] is not None],external_unassigned=[v for v in external if v['source_community'] is None],
            ambiguous_members=[i+1 for i in members if rows[i]['ambiguous']]))
    return result


def rewired(a,rng):
    b=a.copy();edges=[tuple(map(int,e)) for e in np.argwhere(np.triu(a,1))]
    if len(edges)<2:return b,0
    accepted=0
    for _ in range(max(40,len(edges)*30)):
        p,q=rng.choice(len(edges),2,replace=False)
        u,v=edges[p];s,t=edges[q]
        if rng.random()<.5:s,t=t,s
        if len({u,v,s,t})<4 or b[u,t] or b[s,v]:continue
        b[u,v]=b[v,u]=b[s,t]=b[t,s]=False
        b[u,t]=b[t,u]=b[s,v]=b[v,s]=True
        edges[p]=tuple(sorted((u,t)));edges[q]=tuple(sorted((s,v)));accepted+=1
    return b,accepted


def assess(a,gamma=.25,seed=23,repeats=39):
    d=Detector(gamma,seed);d.detect(a)
    values=[];keys=set();swaps=[];rng=np.random.default_rng(seed+7713)
    for _ in range(repeats):
        b,s=rewired(a,rng);keys.add(b.tobytes());swaps.append(s)
        other=Detector(gamma,seed);other.detect(b);values.append(other.score)
    valid=len(keys)>=min(10,repeats) and min(swaps)>0
    p=(1+sum(v>=d.score-1e-9 for v in values))/(repeats+1)
    sensitivity=[]
    for g in (.15,.25,.40):
        other=Detector(g,seed);other.detect(a)
        sensitivity.append({'gamma':g,'communities':len(other.groups),'quality':other.score,
                            'vi_bits':partition_vi(d.raw,other.raw)})
    return {'observed_quality':d.score,'gamma':gamma,'null_quality':values,'null_repeats':repeats,
            'distinct_null_graphs':len(keys),'rewiring_valid':valid,'exploratory_p':p if valid else None,
            'interpretation':('無作為化より強い構造の候補' if p<.05 else '明確な集団構造は未確認') if valid else '無作為化の変化が不足・判定保留',
            'sensitivity':sensitivity,'note':'次数保存ランダム化との探索的比較。社会的集団の存在証明ではない。'}


def reanalyze_snapshot(snapshot,rules=None):
    """Recompute roles from an exported state without rerunning social dynamics."""
    from types import SimpleNamespace
    a=np.asarray(snapshot['a'],bool);raw=np.asarray(snapshot['membership'],int)
    labels=np.asarray(snapshot['partition_ids'],int)
    ids={int(c):set(np.flatnonzero(labels==c)) for c in set(labels) if c>=0}
    detector=SimpleNamespace(raw=raw,labels=labels,ids=ids,ambiguous=np.asarray(snapshot['ambiguous'],bool),options=snapshot.get('options',[]))
    return roles(a,np.asarray(snapshot['x'],float),detector,{k:np.asarray(v) for k,v in snapshot['traits'].items()},rules=rules)
