"""Paired, predeclared policy comparisons. Does not change the application model."""
import argparse
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vendor'))
from model import Simulation
from social_dynamics import MODES
from experiments.run_social_dynamics import digest

POLICIES = ('none', 'help_once', 'help_burst', 'help_spaced', 'help_weak',
            'help_strong', 'help_new', 'harm_once', 'harm_burst', 'gossip_burst', 'repair')


def prepare(seed, density, warmup, trust='natural'):
    sim = Simulation(40, seed, settings=MODES['adaptive'] | {'density': density})
    for _ in range(warmup):
        sim.step(enforce_limit=False)
    if trust != 'natural':
        for w in (sim.world, sim.base):
            w.social.trust[:] = w.a * {'low': .15, 'high': .85}[trust]
            w.capture('experimental_trust_override')
    assert digest(sim.world) == digest(sim.base)
    return sim


def targets(w):
    neighbors = np.flatnonzero(w.a[0]).tolist()
    others = [i for i in range(1, len(w.x)) if not w.a[0, i]]
    # Fixed at intervention start, including deterministic ties by person ID.
    weak = min(neighbors, key=lambda j: (w.x[j, 0] - w.traits['cut'][j], j)) if neighbors else None
    strong = max(neighbors, key=lambda j: (w.social.trust[j, 0], -j)) if neighbors else None
    new = max(others, key=lambda j: (min(w.x[0,j]-w.traits['form'][0], w.x[j,0]-w.traits['form'][j]), -j)) if others else None
    subject = max(neighbors or list(range(1, len(w.x))), key=lambda j: (w.a[j].sum(), -j))
    return dict(weak=weak, strong=strong, new=new, subject=subject)


def intervene(s, policy, offset, selected):
    burst = offset in range(5)
    spaced = offset in (0, 4, 8, 12, 16)
    if policy == 'none':
        return
    if policy == 'repair':
        if offset == 0:
            s.act_to_neighbors('harm', 0, 1.)
        elif offset in (4, 8, 12, 16):
            s.act_to_neighbors('help', 0, 1.)
    elif policy in ('help_weak', 'help_strong', 'help_new'):
        j = selected[policy.split('_')[1]]
        if spaced and j is not None:
            s.act('help', 0, j, 1.)
    elif policy == 'gossip_burst':
        if burst:
            s.gossip_to_neighbors(0, selected['subject'], 1.)
    elif ((policy.endswith('_once') and offset == 0) or
          (policy.endswith('_burst') and burst) or (policy == 'help_spaced' and spaced)):
        s.act_to_neighbors('harm' if policy.startswith('harm') else 'help', 0, 1.)


def metrics(w, initial_neighbors, since, subject):
    n = len(w.x)
    other = np.arange(1, n)
    mask = ~np.eye(n, dtype=bool)
    degrees = w.a.sum(axis=1)
    logs = [e for e in w.timeline if e['step'] > since]
    rumors = [e for e in w.events if e['kind'] == 'gossip' and e['step'] >= since]
    seen = set()
    for e in rumors:
        seen.update(int(i) for i in np.flatnonzero(e['seen']) if i != e['actor'])
    return dict(ego_degree=int(degrees[0]), ego_in_liking=float(w.x[other,0].mean()),
                ego_in_trust=float(w.social.trust[other,0].mean()),
                retained=int(w.a[0, initial_neighbors].sum()),
                new_ties=int(w.a[0].sum()-w.a[0, initial_neighbors].sum()),
                ties=int(w.a.sum()//2), isolates=int((degrees==0).sum()),
                communities=sum(len(g)>=3 for g in w.detector.groups),
                negative_liking=float(np.maximum(-w.x[mask],0).mean()),
                subject_liking=float(w.x[np.arange(n)!=subject,subject].mean()),
                exchanges=sum(e['kind']=='social_invitation' and e['outcome']=='accepted' for e in logs),
                ego_exchanges=sum(e['kind']=='social_invitation' and e['outcome']=='accepted' and (e['actor']==1 or e['target']==1) for e in logs),
                gossip_unique_reach=len(seen), gossip_events=len(rumors))


def execute(initial, policy, steps):
    # Modules are immutable services; all state arrays, detectors, logs and worlds
    # are copied, including the SocialDynamics -> World back-reference.
    s = copy.deepcopy(initial, {id(initial.measure): initial.measure})
    start = s.iteration
    initial_digest = digest(s.world)
    selected = targets(s.world)
    neighbors = np.flatnonzero(s.world.a[0])
    row = dict(seed=s.seed, split='discovery' if s.seed < 100 else 'validation',
               density=s.p['density'], policy=policy, initial_digest=initial_digest,
               initial_degree=len(neighbors), initial_in_liking=float(s.world.x[1:,0].mean()),
               initial_neighbor_trust=float(s.world.social.trust[neighbors,0].mean()) if len(neighbors) else 0.,
               initial_min_cut_margin=float(min((s.world.x[j,0]-s.world.traits['cut'][j] for j in neighbors),default=0.)),
               weak_target=selected['weak'], strong_target=selected['strong'], new_target=selected['new'],
               gossip_subject=selected['subject'], steps=steps, warmup=start)
    actions = []
    for offset in range(steps):
        before = len(s.world.timeline)
        intervene(s, policy, offset, selected)
        actions.extend(e.copy() for e in s.world.timeline[before:] if e['kind']=='action_scheduled')
        s.step(enforce_limit=False)
        if offset == 19:
            row['degree_delta_t20'] = int(s.world.a[0].sum()-s.base.a[0].sum())
    assert digest(initial.world) == initial_digest, 'Source fixture mutated'
    m, b = [metrics(w, neighbors, start, selected['subject']) for w in (s.world,s.base)]
    row.update({f'final_{k}':v for k,v in m.items()})
    row.update({f'baseline_{k}':v for k,v in b.items()})
    row.update({f'delta_{k}':m[k]-b[k] for k in m})
    row.update({f'compare_{k}':s.history[-1][k] for k in ('difference','tie_difference','vi_bits','trust_difference')})
    row['final_digest'], row['baseline_digest'] = digest(s.world), digest(s.base)
    row['status'] = s.status
    row['observation_end'] = {'absorbed':'absorbing','stable':'observed_stable'}.get(s.status,'not_converged')
    row['third_party_edge_changes'] = int(np.triu(s.world.a[1:,1:] != s.base.a[1:,1:],1).sum())
    row['other_people_losing_degree'] = int((s.world.a.sum(1)[1:] < s.base.a.sum(1)[1:]).sum())
    row['ambiguous_people'] = int(s.world.detector.ambiguous.sum())
    direct = [e for e in s.world.events if e['step']>=start and e['kind'] in ('help','harm')]
    row['effective_direct_strength'] = float(sum(e['strength'] for e in direct))
    return row, s, actions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds', default='0,1,2,3,4,5,100,101,102,103,104,105')
    p.add_argument('--densities', default='.05,.10,.20')
    p.add_argument('--policies', default=','.join(POLICIES))
    p.add_argument('--steps', type=int, default=60)
    p.add_argument('--warmup', type=int, default=10)
    p.add_argument('--trust-check', action='store_true')
    p.add_argument('--output', type=Path, default=ROOT/'docs/experiments/conditions-and-policies')
    args = p.parse_args()
    seeds = [int(s) for s in args.seeds.split(',')]
    densities = [float(s) for s in args.densities.split(',')]
    policies = args.policies.split(',')
    if any(s not in POLICIES for s in policies) or args.steps < 20 or args.warmup < 0:
        p.error('Unknown policy or invalid horizon (steps >=20, warmup >=0).')
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    metadata = dict(seeds=seeds,densities=densities,policies=policies,steps=args.steps,warmup=args.warmup,
        mode='adaptive',n=40,actor_python_id=0,strength=1.,trust_check=args.trust_check,
        splits='seeds <100 discovery; >=100 validation; all policies fixed before running',
        schedule='once:0; burst:0..4; spaced/weak/strong/new:0,4,8,12,16; repair:harm0+help4,8,12,16',
        target_rule='weak=min receiver cut margin; strong=max receiver trust; new=max min bilateral join margin; gossip=highest-degree original neighbor',
        interpretation='finite-horizon model experiment, not empirical social advice; paired complete initial state and keyed external random draws',
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('model.py','social_dynamics.py','community.py','experiments/run_policy_study.py')},
        python=sys.version,numpy=np.__version__)
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    rows=[]; actions=[]; started=time.monotonic()
    conditions=[(seed,d,'natural',policies) for seed in seeds for d in densities]
    if args.trust_check:
        conditions += [(seed,.1,t,['harm_once','harm_burst','help_spaced','gossip_burst']) for seed in seeds for t in ('low','high')]
    replay_sample=None
    for seed,density,trust,choices in conditions:
        initial=prepare(seed,density,args.warmup,trust)
        # Save actual intervention-time inputs, not just a seed.
        with gzip.open(out/f'initial_s{seed}_d{density}_t{trust}.json.gz','wt',encoding='utf-8') as f:
            json.dump(dict(seed=seed,settings=initial.p,time=initial.iteration,digest=digest(initial.world),
                x=initial.world.x.tolist(),a=initial.world.a.tolist(),trust=initial.world.social.trust.tolist(),
                traits={k:v.tolist() for k,v in initial.world.traits.items()}),f)
        control_digest=None
        for policy in choices:
            row,s,requests=execute(initial,policy,args.steps)
            row['trust_condition']=trust
            if control_digest is None:control_digest=row['baseline_digest']
            assert control_digest==row['baseline_digest'], 'Control depends on policy'
            if policy=='none':assert row['final_digest']==row['baseline_digest']
            rows.append(row)
            actions.append(dict(seed=seed,density=density,trust_condition=trust,policy=policy,requests=requests))
            with (out/'runs.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,list(row));w.writeheader();w.writerows(rows)
            if replay_sample is None and policy=='help_spaced':
                replay_sample=(seed,density,trust,policy,row.copy())
        print(f'{len(rows)} runs; seed={seed} density={density} trust={trust}; elapsed={time.monotonic()-started:.1f}s',flush=True)
    (out/'actions.json').write_text(json.dumps(actions,indent=2),encoding='utf-8')
    replay=None
    if replay_sample:
        seed,density,trust,policy,expected=replay_sample
        row,_,_=execute(prepare(seed,density,args.warmup,trust),policy,args.steps)
        row['trust_condition']=trust
        assert row==expected,'Replay mismatch'
        replay=dict(seed=seed,density=density,trust=trust,policy=policy,exact_match=True)
    (out/'verification.json').write_text(json.dumps(dict(runs=len(rows),initial_pair_equality=True,
        null_interventions_exact=True,baseline_independent_of_policy=True,replay=replay,
        elapsed_seconds=time.monotonic()-started),indent=2),encoding='utf-8')


if __name__=='__main__':main()
