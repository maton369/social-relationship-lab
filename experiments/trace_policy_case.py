"""Replay a specified published condition and save compact, inspectable evidence."""
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
from run_policy_study import prepare,execute,ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--density',type=float,default=.1)
    p.add_argument('--policy',required=True)
    p.add_argument('--steps',type=int,default=240)
    p.add_argument('--output',type=Path,default=ROOT/'docs/experiments/conditions-and-policies/cases')
    a=p.parse_args()
    row,s,actions=execute(prepare(a.seed,a.density,10),a.policy,a.steps)
    name=f's{a.seed}_d{a.density}_{a.policy}_t{a.steps}'
    a.output.mkdir(parents=True,exist_ok=True)
    # Full states, events, matching controls and histories retained for inspection.
    with gzip.open(a.output/(name+'.json.gz'),'wt',encoding='utf-8') as f:
        json.dump(s.snapshot(),f,ensure_ascii=False,allow_nan=False)
    ego=lambda w:sorted((np.flatnonzero(w.a[0])+1).tolist())
    chosen=s.world.events
    inv=lambda w:{(e['step'],e['actor'],e['target']):e for e in w.timeline if e['kind']=='social_invitation' and e['step']>10}
    intervention,baseline=inv(s.world),inv(s.base)
    blocked=[]
    for key,e in baseline.items():
        f=intervention.get(key)
        if e['outcome']=='accepted' and f and f['outcome']=='no_time' and (key[1]==1 or key[2]==1):
            blocked.append(dict(step=key[0],actor=key[1],target=key[2],baseline=e['outcome'],intervention=f['outcome']))
    after=[v for v in s.world.snapshots if v['step']==10][-1]
    before_neighbors=set((np.flatnonzero(after['a'][0])+1).tolist())
    now,control=set(ego(s.world)),set(ego(s.base))
    info=dict(comparison=row,requests=actions,initial_neighbors=sorted(before_neighbors),
        intervention_neighbors=sorted(now),baseline_neighbors=sorted(control),
        baseline_only_neighbors=sorted(control-now),intervention_only_neighbors=sorted(now-control),
        original_neighbors_lost=sorted(before_neighbors-now),
        same_proposal_accepted_in_control_no_time_in_intervention=blocked,
        note='Matching proposal outcomes document scheduling effects, not a unique causal decomposition of the final network.',
        events=[dict(id=e['id'],kind=e['kind'],target=e['target']+1,step=e['step'],strength=e['strength'],
            reached=len(np.flatnonzero(e['seen']))-1,initial_credits=e.get('initial_credits'),
            depth_max=int(e['depth'].max())) for e in chosen])
    (a.output/(name+'-summary.json')).write_text(json.dumps(info,indent=2),encoding='utf-8')
    # One line per tick (snapshots also include extra action captures).
    wb={v['step']:v for v in s.world.snapshots}
    bb={v['step']:v for v in s.base.snapshots}
    series=[]
    for t in sorted(wb.keys() & bb.keys()):
        if t<10:continue
        w,b=wb[t],bb[t]
        series.append(dict(step=t-10,degree=int(w['a'][0].sum()),baseline_degree=int(b['a'][0].sum()),
            incoming_liking=float(w['x'][1:,0].mean()),baseline_liking=float(b['x'][1:,0].mean())))
    (a.output/(name+'-series.json')).write_text(json.dumps(series,indent=2),encoding='utf-8')
    print(json.dumps({k:info[k] for k in ('initial_neighbors','intervention_neighbors','baseline_neighbors','original_neighbors_lost','baseline_only_neighbors')},indent=2))


if __name__=='__main__':main()
