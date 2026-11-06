"""Event-driven social model. Parameters are explicit artistic hypotheses.

X (directed appraisal), A (mutual ties), event knowledge K, and measured
CPM communities are distinct. Community labels/positions never affect X/A.
"""
import hashlib
import numpy as np

DEFAULTS=dict(density=.10,form=.55,cut=.25,receive=.65,spread=.55,
              q0=.03,qtri=.10,pmax=.70,eta_v=.50,eta_o=.40,eta_r=.30,
              omega=.65,gamma=.25,witnesses=2,window=10,tolerance=.005,limit=100,
              community_min=3,hub_min_size=4,hub_degree=3,hub_ratio=.60,high_liking=.50)


def draw(seed,t,kind,i,j,event=0):
    raw=('%d|%d|%d|%d|%d|%d'%(seed,t,kind,i,j,event)).encode('ascii')
    return (int.from_bytes(hashlib.blake2b(raw,digest_size=8).digest(),'little')>>11)/2**53


def update_ties(x,a,form,cut,opportunity):
    leave=(x<=cut[:,None]);want=(x>=form[:,None])
    result=(a & ~(leave|leave.T)) | (~a & opportunity & want & want.T)
    np.fill_diagonal(result,False)
    return result


class World:
    def __init__(self,x,a,traits,settings,seed,measure):
        self.x=x.copy();self.a=a.copy();self.initial_x=x.copy();self.initial_a=a.copy()
        self.traits={k:v.copy() for k,v in traits.items()}
        self.p=dict(settings);self.seed=seed;self.measure=measure
        self.detector=measure.Detector(self.p['gamma'],seed)
        self.detector.detect(self.a,0)
        self.events=[];self.timeline=[];self.snapshots=[];self._last_tie_pairs=set();self._role_cache=None;self.time=0;self.added=[];self.removed=[];self.transmissions=[]
        self.formed=np.zeros(len(x),int);self.lost=np.zeros(len(x),int)
        self.received=np.zeros(len(x),int);self.moves=np.zeros(len(x),int)
        self.x_quiet=self.a_quiet=self.c_quiet=0;self.residual=0.
        self.initial_roles=self.role_rows(initial=False)
        self.capture('initial')

    def role_rows(self,initial=True):
        if initial and self._role_cache is not None:return self._role_cache
        rules={k:self.p[k] for k in self.measure.ROLE_DEFAULTS}
        rows=self.measure.roles(self.a,self.x,self.detector,self.traits,self.initial_a,
            self.initial_roles if initial else None,self.formed,self.lost,self.received,self.moves,rules)
        for i,r in enumerate(rows):
            r.update(actions_initiated=sum(e['actor']==i for e in self.events),
                actions_received=sum(e['target']==i and e['kind']!='gossip' for e in self.events),
                actions_observed=sum(i in e['witnesses'] for e in self.events),
                successful_transmissions=sum(i+1 in item['sources'] for e in self.events for item in e['receipts']),
                transmission_credit=sum(1/len(item['sources']) for e in self.events for item in e['receipts'] if i+1 in item['sources']),
                unique_people_informed=len({item['person'] for e in self.events for item in e['receipts'] if i+1 in item['sources']}),
                ties_reformed=sum(v['kind']=='tie_formed' and v.get('reformed',False) and i+1 in v['people'] for v in self.timeline),
                lost_people=sorted({j for v in self.timeline if v['kind']=='tie_cut' and i+1 in v['people'] for j in v['people'] if j!=i+1}))
        if initial:self._role_cache=rows
        return rows

    def capture(self,reason):
        self._role_cache=None
        self.snapshots.append(dict(step=self.time,reason=reason,x=self.x.copy(),a=self.a.copy(),
            membership=self.detector.raw.copy(),partition_ids=self.detector.labels.copy(),
            cpm_quality=self.detector.score,gamma=self.detector.gamma,
            ambiguous=self.detector.ambiguous.copy(),options=list(self.detector.options),
            settings=dict(self.p),
            traits={k:v.copy() for k,v in self.traits.items()}))

    def settle_relations(self,opportunity,trigger=None):
        before=self.a.copy();prev=self.detector.labels.copy();raw=self.detector.raw.copy()
        self.a=update_ties(self.x,self.a,self.traits['form'],self.traits['cut'],opportunity)
        add=self.a & ~before;remove=before & ~self.a
        self.formed+=add.sum(axis=1);self.lost+=remove.sum(axis=1)
        self.added=[tuple(map(int,p)) for p in np.argwhere(np.triu(add,1))]
        self.removed=[tuple(map(int,p)) for p in np.argwhere(np.triu(remove,1))]
        self.detector.detect(self.a,self.time)
        changed=np.any((raw[:,None]==raw[None,:])!=(self.detector.raw[:,None]==self.detector.raw[None,:]),axis=1)
        self.moves+=changed.astype(int)
        self._role_cache=None
        for kind,pairs in [('tie_formed',self.added),('tie_cut',self.removed)]:
            for i,j in pairs:
                pair=(i,j);reformed=pair in self._last_tie_pairs
                self._last_tie_pairs.add(pair)
                self.timeline.append(dict(step=self.time,kind=kind,people=[i+1,j+1],trigger=trigger,
                    appraisal_ij=float(self.x[i,j]),appraisal_ji=float(self.x[j,i]),
                    cut_i=float(self.traits['cut'][i]),cut_j=float(self.traits['cut'][j]),reformed=reformed if kind=='tie_formed' else False))
        for i in np.flatnonzero(changed):
            before_members=np.flatnonzero(raw==raw[i]);after_members=np.flatnonzero(self.detector.raw==self.detector.raw[i])
            before_major=len(before_members)>=self.p['community_min'];after_major=len(after_members)>=self.p['community_min']
            kind='join' if after_major and not before_major else 'leave' if before_major and not after_major else 'membership_structure_changed'
            self.timeline.append(dict(step=self.time,kind=kind,person=int(i)+1,
                before_members=(before_members+1).tolist(),after_members=(after_members+1).tolist(),
                notice='構造的所属の変化。本人の意思を表さない。'))
        self.a_quiet=self.a_quiet+1 if not np.any(add|remove) else 0
        self.c_quiet=self.c_quiet+1 if not changed.any() else 0

    def delta_for(self,event,i,credit):
        u,v=event['actor'],event['target'];strength=event['strength']
        change=np.zeros_like(self.x)
        if i==u:return change
        s=self.traits['receive'][i]
        if event['kind']=='gossip':change[i,v]=-self.p['eta_r']*strength*s*credit
        elif i!=v:
            sign=1. if event['kind']=='help' else -1.
            response=1.-self.p['omega']+self.p['omega']*self.x[i,v]
            change[i,u]=self.p['eta_o']*strength*s*credit*sign*response
        return change

    def _prepare_action(self,kind,u,v,strength,event_id,witnesses=None):
        n=len(self.x)
        if u==v or not(0<=u<n and 0<=v<n):raise ValueError('別々の行動者と対象を選んでください。')
        if kind not in ('help','harm','gossip'):raise ValueError('Unknown action')
        e={'id':event_id,'kind':kind,'actor':int(u),'target':int(v),
           'strength':float(np.clip(strength,0,1)),'step':self.time,'seen':np.zeros(n,bool),
           'frontier':[],'depth':np.full(n,-1,int),'receipts':[]}
        if witnesses is None:
            eligible=np.flatnonzero(self.a[u] | (self.a[v] if kind!='gossip' else False))
            eligible=[int(i) for i in eligible if i not in (u,v)]
            eligible.sort(key=lambda i:draw(self.seed,self.time,3,u,i,e['id']))
            witnesses=eligible[:int(self.p['witnesses'])]
        else:
            witnesses=sorted(set(int(i) for i in witnesses if i not in (u,v)))
            if any(not 0<=i<n for i in witnesses):raise ValueError('Invalid receiver')
        informed=[u]+([v] if kind!='gossip' else [])+witnesses
        e['seen'][informed]=True;e['depth'][informed]=0;e['frontier']=informed
        delta=np.zeros_like(self.x)
        if kind!='gossip':delta[v,u]=(1 if kind=='help' else -1)*self.p['eta_v']*e['strength']
        for i in witnesses:
            credit=(1.+self.x[i,u])/2 if kind=='gossip' else 1.
            delta+=self.delta_for(e,i,credit)
        e['witnesses']=witnesses;e['changed_appraisals']=int(np.count_nonzero(abs(delta)>1e-12))
        return e,delta,informed

    def act(self,kind,u,v,strength,witnesses=None):
        return self.act_many(kind,u,[v],strength,witnesses=witnesses)

    def act_many(self,kind,u,targets,strength,witnesses=None,contact=True):
        # Freeze both evaluations and adjacency until every action is prepared.
        # A severed tie or clipping in one action cannot change another action.
        targets=sorted(set(int(v) for v in targets))
        prepared=[self._prepare_action(kind,u,v,strength,len(self.events)+k+1,witnesses)
                  for k,v in enumerate(targets)]
        if not prepared:return []
        before_x=self.x.copy();delta=np.zeros_like(self.x);opportunity=np.zeros_like(self.a)
        inputs={}
        batch_id=prepared[0][0]['id']
        for e,change,informed in prepared:
            e['batch_id']=batch_id
            delta+=change
            self.received[[i for i in informed if i!=u]]+=1
            self.events.append(e)
            self.timeline.append(dict(step=self.time,kind='action',event=e['id'],batch_id=batch_id,
                action=kind,actor=int(u)+1,target=e['target']+1,strength=e['strength']))
            for i in e['witnesses']:self.timeline.append(dict(step=self.time,kind='observation',event=e['id'],person=i+1))
            for i,j in np.argwhere(abs(change)>1e-12):
                inputs.setdefault((int(i),int(j)),[]).append(dict(event=e['id'],requested_delta=float(change[i,j]),
                    mechanism='direct_effect' if i==e['target'] and kind!='gossip' else 'initial_observation'))
            if contact:opportunity[u,e['target']]=opportunity[e['target'],u]=True
        self.x=np.clip(before_x+delta,-1,1);np.fill_diagonal(self.x,0.)
        self.residual=float(abs(self.x-before_x).max())
        for i,j in np.argwhere(abs(self.x-before_x)>1e-12):
            self.timeline.append(dict(step=self.time,kind='appraisal_update',person=int(i)+1,target=int(j)+1,
                event=inputs[(int(i),int(j))][0]['event'] if len(inputs[(int(i),int(j))])==1 else None,
                mechanism=inputs[(int(i),int(j))][0]['mechanism'] if len(inputs[(int(i),int(j))])==1 else 'simultaneous_actions',
                inputs=inputs[(int(i),int(j))],batch_id=batch_id,before=float(before_x[i,j]),after=float(self.x[i,j])))
        self.settle_relations(opportunity,dict(kind='direct_action',events=[e['id'] for e,_,_ in prepared],batch_id=batch_id))
        self.x_quiet=self.a_quiet=self.c_quiet=0
        self.capture('action')
        return [e['id'] for e,_,_ in prepared]

    def advance(self):
        self.time+=1;old=self.x.copy();a=self.a.copy();n=len(a)
        total=np.zeros_like(self.x);self.transmissions=[];inputs=[]
        for e in self.events:
            arrivals={}
            for source in e['frontier']:
                for receiver in np.flatnonzero(a[source] & ~e['seen']):
                    receiver=int(receiver)
                    prob=self.p['pmax']*self.traits['spread'][source]
                    success=draw(self.seed,self.time,2,source,receiver,e['id'])<prob
                    self.timeline.append(dict(step=self.time,kind='transmission_attempt',event=e['id'],
                        source=int(source)+1,person=receiver+1,success=bool(success)))
                    if success:
                        arrivals.setdefault(receiver,[]).append(source)
            for receiver,sources in arrivals.items():
                credit=max((1.+old[receiver,s])/2 for s in sources)
                contribution=self.delta_for(e,receiver,credit);total+=contribution
                for i,j in np.argwhere(abs(contribution)>1e-12):
                    inputs.append(dict(person=int(i)+1,target=int(j)+1,event=e['id'],
                        sources=[s+1 for s in sources],requested_delta=float(contribution[i,j])))
                depth=1+min(int(e['depth'][s]) for s in sources)
                e['depth'][receiver]=depth;e['seen'][receiver]=True;self.received[receiver]+=1
                e['receipts'].append({'step':self.time,'person':receiver+1,'sources':[s+1 for s in sources],
                                      'credit':float(credit),'depth':depth})
                self.transmissions.extend((s,receiver) for s in sources)
                self.timeline.append(dict(kind='transmission',event=e['id'],**e['receipts'][-1]))
            e['frontier']=sorted(arrivals)
        self.x=np.clip(old+total,-1,1);np.fill_diagonal(self.x,0.)
        for i,j in np.argwhere(abs(self.x-old)>1e-12):
            self.timeline.append(dict(step=self.time,kind='appraisal_update',person=int(i)+1,target=int(j)+1,
                mechanism='information',before=float(old[i,j]),after=float(self.x[i,j]),
                inputs=[item for item in inputs if item['person']==i+1 and item['target']==j+1]))
        self.residual=float(abs(self.x-old).max())
        common=a.astype(int)@a.astype(int)
        opportunity=np.zeros_like(a)
        for i in range(n):
            for j in range(i+1,n):
                q=min(1.,self.p['q0']+self.p['qtri']*(common[i,j]>0))
                opportunity[i,j]=opportunity[j,i]=draw(self.seed,self.time,1,i,j)<q
        self.settle_relations(opportunity,dict(kind='synchronous_update',arrivals=[v for v in self.timeline if v['step']==self.time and v['kind']=='transmission']))
        self.x_quiet=self.x_quiet+1 if self.residual<self.p['tolerance'] else 0
        self.capture('step')

    @property
    def pending(self):return sum(len(e['frontier']) for e in self.events)

    @property
    def possible_contacts(self):
        want=self.x>=self.traits['form'][:,None]
        eligible=want & want.T & ~self.a
        np.fill_diagonal(eligible,False)
        if self.p['q0']==0:
            common=self.a.astype(int)@self.a.astype(int)
            eligible &= (common>0) & (self.p['qtri']>0)
        return int(np.triu(eligible,1).sum())


class Simulation:
    def __init__(self,n=40,seed=23,settings=None,measure=None):
        if measure is None:
            import community as measure
        self.measure=measure;self.n=int(n);self.seed=int(seed)
        if not 4<=self.n<=80:raise ValueError('Population must be 4..80')
        self.p=DEFAULTS|dict(settings or {})
        rng=np.random.default_rng(seed)
        clip=lambda x,lo,hi:np.clip(x,lo,hi)
        traits={'form':clip(rng.normal(self.p['form'],.07,n),.1,.95),
                'cut':clip(rng.normal(self.p['cut'],.05,n),-.5,.9),
                'receive':clip(rng.normal(self.p['receive'],.15,n),0,1),
                'spread':clip(rng.normal(self.p['spread'],.15,n),0,1)}
        traits['cut']=np.minimum(traits['cut'],traits['form']-.10)
        a=np.triu(rng.random((n,n))<self.p['density'],1);a|=a.T
        x=clip(rng.normal(0,.35,(n,n)),-1,1)
        x[a]=rng.uniform(.65,.90,int(a.sum()));np.fill_diagonal(x,0.)
        self.world=World(x,a,traits,self.p,seed,measure)
        self.base=World(x,a,traits,self.p,seed,measure)
        self.status='ready';self.history=[];self.analysis=None
        self.record()

    @property
    def iteration(self):return self.world.time

    def act(self,kind,actor,target,strength=.8):
        self.world.act(kind,int(actor),int(target),strength)
        self.status='running';self.analysis=None;self.record()

    def act_to_neighbors(self,kind,actor,strength=.8):
        if kind not in ('help','harm'):raise ValueError('Use an explicit subject for gossip.')
        actor=int(actor)
        if not 0<=actor<self.n:raise ValueError('Invalid actor')
        targets=np.flatnonzero(self.world.a[actor]).tolist()
        events=self.world.act_many(kind,actor,targets,strength)
        if events:self.status='running';self.analysis=None;self.record()
        return targets

    def gossip_to_neighbors(self,actor,subject,strength=.8):
        actor,subject=int(actor),int(subject)
        if actor==subject or not(0<=actor<self.n and 0<=subject<self.n):
            raise ValueError('噂を話す人物と、噂の対象は別の人物にしてください。')
        receivers=[int(i) for i in np.flatnonzero(self.world.a[actor]) if i!=subject]
        if not receivers:return []
        # The subject is not a receiver. Hearing a rumor is not meeting its subject.
        self.world.act_many('gossip',actor,[subject],strength,witnesses=receivers,contact=False)
        self.status='running';self.analysis=None;self.record()
        return receivers

    def step(self,enforce_limit=True):
        if enforce_limit and self.iteration>=self.p['limit']:
            self.status='limit';return False
        self.world.advance();self.base.advance();self.record();self.analysis=None
        window=self.p['window']
        stable=all(min(w.x_quiet,w.a_quiet,w.c_quiet)>=window and not w.pending for w in (self.world,self.base))
        self.status=('absorbed' if not self.world.possible_contacts and not self.base.possible_contacts else 'stable') if stable else 'running'
        if enforce_limit and self.iteration>=self.p['limit'] and not stable:self.status='limit'
        return True

    def record(self):
        w,b=self.world,self.base
        mask=~np.eye(self.n,dtype=bool)
        self.history.append({'step':self.iteration,'difference':float(abs(w.x-b.x)[mask].mean()),
            'tie_difference':int(np.triu(w.a!=b.a,1).sum()),'vi_bits':self.measure.partition_vi(w.detector.raw,b.detector.raw),
            'communities':sum(len(g)>=self.p['community_min'] for g in w.detector.groups),'baseline_communities':sum(len(g)>=self.p['community_min'] for g in b.detector.groups),
            'ties':int(w.a.sum()//2),'isolated':int((w.a.sum(axis=1)==0).sum()),
            'max_change':w.residual,'pending':w.pending})

    def edit_person(self,i,form,cut,receive,spread):
        if cut>=form:raise ValueError('成立閾値は切断閾値より高くしてください。')
        for w in (self.world,self.base):
            for name,value in [('form',form),('cut',cut),('receive',receive),('spread',spread)]:w.traits[name][i]=value
            w.settle_relations(np.zeros_like(w.a))
            w.x_quiet=w.a_quiet=w.c_quiet=0
            w.timeline.append(dict(step=w.time,kind='attribute_edit',person=i+1,values=dict(form=form,cut=cut,receive=receive,spread=spread)))
            w.capture('attribute_edit')
        self.status='ready';self.analysis=None
        self.record()

    def summary(self,with_null=False):
        rows=self.world.role_rows();baseline=self.base.role_rows()
        aggregates={}
        for flag in ('hub','multi_community_connector','structural_broker','isolated','high_liking','internal_peripheral','ambiguous'):
            selected=[r for r in rows if r[flag]]
            aggregates[flag]={'n':len(selected),'people':[r['person'] for r in selected],
                **{key:(float(np.mean([r[key] for r in selected])) if selected else None)
                   for key in ('formation','cut','receptivity','spread','initial_degree')}}
        return {'status':self.status,'step':self.iteration,'people':rows,'baseline_people':baseline,
            'role_attributes':aggregates,'communities':self.measure.community_rows(self.world.a,self.world.detector,rows,{k:self.p[k] for k in self.measure.ROLE_DEFAULTS}),
            'analysis_version':self.measure.ANALYSIS_VERSION,'rules':{k:self.p[k] for k in self.measure.ROLE_DEFAULTS},
            'person_comparison':[dict(person=r['person'],baseline=b,action=r,changed=r['roles']!=b['roles'] or r['degree']!=b['degree'] or r['brokerage_disconnected_pairs']!=b['brokerage_disconnected_pairs']) for r,b in zip(rows,baseline)],
            'community_events':self.world.detector.events,'pending_community_events':[
                {k:v for k,v in e.items() if k!='partition'} for e in self.world.detector.pending],
            'quality_check':self.measure.assess(self.world.a,self.p['gamma'],self.seed) if with_null else None,
            'pending_information':self.world.pending,'possible_future_contacts':self.world.possible_contacts,
            'notice':'一試行の記述的分析。属性と役割の因果関係は断定しない。'}

    def snapshot(self):
        def events(w):
            result=[]
            for event in w.events:
                e={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in event.items()}
                for key in ('actor','target'):e[key]+=1
                for key in ('witnesses','frontier'):e[key]=[i+1 for i in e[key]]
                result.append(e)
            return result
        return {'version':2,'model_version':'2.2','analysis_version':self.measure.ANALYSIS_VERSION,'seed':self.seed,'settings':self.p,'status':self.status,'step':self.iteration,
            'indexing':'人物IDは1始まり。行列・人物別配列の位置はID−1。所属ラベルは人物IDではない。',
            'initial_appraisals':self.world.initial_x.tolist(),'initial_ties':self.world.initial_a.astype(int).tolist(),
            'appraisals':self.world.x.tolist(),'baseline_appraisals':self.base.x.tolist(),
            'ties':self.world.a.astype(int).tolist(),'baseline_ties':self.base.a.astype(int).tolist(),
            'events':events(self.world),'history':self.history,'analysis':self.analysis or self.summary(),
            'timeline':self.world.timeline,'baseline_timeline':self.base.timeline,
            'snapshots':self.serial_snapshots(self.world),'baseline_snapshots':self.serial_snapshots(self.base)}

    @staticmethod
    def serial_snapshots(world):
        return [{k:v.tolist() if isinstance(v,np.ndarray) else {n:a.tolist() for n,a in v.items()} if k=='traits' else v for k,v in snap.items()} for snap in world.snapshots]
