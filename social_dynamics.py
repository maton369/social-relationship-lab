"""Optional social mechanisms inspired by research, with independent prototype rules.

Trust is not liking. A budget is time spent, not degree. All background decisions
read a frozen round state; keyed random draws are shared across comparison worlds.
"""
import numpy as np

DYNAMICS_DEFAULTS = dict(history_enabled=False, budget_enabled=False,
    autonomous_enabled=False, social_budget=1., trust_learning=.18,
    trust_protection=.85, trust_decay=.003, social_gain=.10,
    rejection_loss=.035, maintenance_decay=.002, exploration=.18,
    conflict_discount=.35)

MODES = {
    'legacy': dict(history_enabled=False, budget_enabled=False, autonomous_enabled=False),
    'history': dict(history_enabled=True, budget_enabled=False, autonomous_enabled=False),
    'budget': dict(history_enabled=True, budget_enabled=True, autonomous_enabled=False),
    'adaptive': dict(history_enabled=True, budget_enabled=True, autonomous_enabled=True),
}


class SocialDynamics:
    def __init__(self, world, draw):
        self.world, self.draw = world, draw
        n = len(world.x)
        # Synthetic prior trust for existing ties. These are not observed events.
        self.trust = np.array([[.2+.6*draw(world.seed,0,11,i,j)
                                if world.a[i,j] else 0. for j in range(n)] for i in range(n)])
        self.initial_trust = self.trust.copy()
        self.experiences = np.zeros((n,n),int)
        self.remaining = np.full(n,float(world.p['social_budget']))
        self.last_spent = np.zeros(n)
        self.trust_quiet = 0
        self.last_trust_change = 0.

    @property
    def active(self):
        p=self.world.p
        return bool(p['autonomous_enabled'] or (p['history_enabled'] and p['trust_decay']>0))

    def strength(self, actor, requested, count):
        if not count:return 0.
        if not self.world.p['budget_enabled']:return float(np.clip(requested,0,1))
        value=min(float(np.clip(requested,0,1)),float(self.remaining[actor])/count)
        self.remaining[actor]=max(0.,self.remaining[actor]-value*count)
        self.last_spent[actor]+=value*count
        return value

    def protection(self, receiver, actor):
        p=self.world.p
        return 1.-p['trust_protection']*self.trust[receiver,actor] if p['history_enabled'] else 1.

    def credibility(self, receiver, source, subject=None, old=None):
        w=self.world;p=w.p
        x=w.x if old is None else old
        if not p['history_enabled']:return float((1+x[receiver,source])/2)
        credit=float(self.trust[receiver,source])
        if subject is not None:
            credit*=1-p['conflict_discount']*max(0.,-float(x[source,subject]))
        return float(np.clip(credit,0,1))

    def learn(self, events):
        w=self.world
        if not w.p['history_enabled']:return
        old=self.trust.copy();delta=np.zeros_like(old)
        for e in events:
            if e['kind']=='gossip':continue
            i,j=e['target'],e['actor'];amount=w.p['trust_learning']*e['strength']
            delta[i,j]+=amount*(1-old[i,j]) if e['kind']=='help' else -amount
            self.experiences[i,j]+=1
        self.trust=np.clip(old+delta,0,1)
        self.last_trust_change=float(np.max(abs(self.trust-old)))
        if self.last_trust_change>=w.p['tolerance']:self.trust_quiet=0
        if np.any(delta):w.timeline.append(dict(step=w.time,kind='trust_update',
            events=[e['id'] for e in events],max_change=self.last_trust_change))

    def begin_round(self):
        self.remaining[:]=self.world.p['social_budget'];self.last_spent[:]=0.

    def background(self, old, adjacency):
        w=self.world;p=w.p;n=len(old)
        delta=np.zeros_like(old);opportunity=np.zeros_like(adjacency)
        trust_old=self.trust.copy();trust_delta=np.zeros_like(old)
        if p['history_enabled']:
            # Strong trust wanes more slowly; this particular curve is our assumption.
            trust_delta-=p['trust_decay']*trust_old*(1-.8*trust_old)
        if not p['autonomous_enabled']:
            self.trust=np.clip(trust_old+trust_delta,0,1)
            self._trust_stability(trust_old)
            return delta,opportunity
        delta-=p['maintenance_decay']*old*adjacency
        # Compute all proposals from OLD X/T/A before allocating anyone's time.
        proposals=[]
        for actor in range(n):
            candidates=[j for j in range(n) if j!=actor]
            explore=self.draw(w.seed,w.time,12,actor,0)<p['exploration']
            def score(j):
                noise=-np.log(-np.log(max(1e-12,min(1-1e-12,self.draw(w.seed,w.time,13,actor,j)))))
                preference=0 if explore else 2*old[actor,j]+1.5*trust_old[actor,j]+.5*adjacency[actor,j]
                return preference+noise
            target=max(candidates,key=score)
            probability=1/(1+np.exp(-(2*old[target,actor]+trust_old[target,actor])))
            accepts=self.draw(w.seed,w.time,14,actor,target)<probability
            proposals.append((actor,target,accepts,float(probability)))
        proposals.sort(key=lambda v:self.draw(w.seed,w.time,15,v[0],0))
        for actor,target,accepts,probability in proposals:
            free=float(min(self.remaining[actor],self.remaining[target]))
            if free<1-1e-9:
                outcome='no_time';cost=0.
            elif accepts:
                outcome='accepted';cost=1.
                self.remaining[[actor,target]]-=cost;self.last_spent[[actor,target]]+=cost
                for i,j in [(actor,target),(target,actor)]:
                    delta[i,j]+=p['social_gain']*cost*(1-old[i,j])
                    trust_delta[i,j]+=p['trust_learning']*cost*(1-trust_old[i,j])
                    self.experiences[i,j]+=1
                opportunity[actor,target]=opportunity[target,actor]=True
            else:
                outcome='rejected';cost=.25
                self.remaining[actor]-=cost;self.last_spent[actor]+=cost
                delta[actor,target]-=p['rejection_loss']*cost*(1+old[actor,target])
            w.timeline.append(dict(step=w.time,kind='social_invitation',actor=actor+1,
                target=target+1,outcome=outcome,acceptance_probability=probability,cost=cost,
                randomness='keyed_by_seed_time_actor_target'))
        self.remaining=np.maximum(self.remaining,0)
        self.trust=np.clip(trust_old+trust_delta,0,1)
        np.fill_diagonal(self.trust,0.)
        self._trust_stability(trust_old)
        return delta,opportunity

    def _trust_stability(self, old):
        self.last_trust_change=float(np.max(abs(self.trust-old)))
        self.trust_quiet=self.trust_quiet+1 if self.last_trust_change<self.world.p['tolerance'] else 0
