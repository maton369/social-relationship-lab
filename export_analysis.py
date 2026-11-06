"""Versioned analysis exports. No dependency on TouchDesigner."""
import csv,json,time
from pathlib import Path


def scalar(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False) if isinstance(value,(dict,list,tuple)) else value


def write_csv(path,rows):
    rows=list(rows)
    fields=list(dict.fromkeys(k for row in rows for k in row)) or ['empty']
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:scalar(v) for k,v in r.items()} for r in rows)


def save(sim,directory):
    folder=Path(directory)/('seed%d_t%03d_%d'%(sim.seed,sim.iteration,time.time_ns()))
    folder.mkdir(parents=True,exist_ok=False)
    data=sim.snapshot();report=data['analysis'];run_id=folder.name
    metadata=dict(run_id=run_id,seed=sim.seed,analysis_time=sim.iteration,
        convergence_status=sim.status,model_version=data['model_version'],analysis_version=data['analysis_version'],
        settings=sim.p,role_rules=report['rules'])
    rows=[];groups=[];connections=[];events=[];runs=[]
    for condition,world,people in [('action',sim.world,report['people']),('baseline',sim.base,report['baseline_people'])]:
        runs.append(dict(metadata,condition=condition,actions=[dict(id=e['id'],kind=e['kind'],actor=e['actor']+1,target=e['target']+1,strength=e['strength'],step=e['step']) for e in world.events]))
        for person in people:
            rows.append(dict(metadata,condition=condition,**person))
            for cid,count in person['community_connections'].items():
                connections.append(dict(run_id=run_id,condition=condition,person=person['person'],community_id=int(cid),
                    is_member=person['community']==int(cid),direct_ties=count,base_status=person['base_status']))
        groups.extend(dict(run_id=run_id,condition=condition,**g) for g in sim.measure.community_rows(world.a,world.detector,people,report['rules']))
        events.extend(dict(run_id=run_id,condition=condition,**e) for e in world.timeline)
        events.extend(dict(run_id=run_id,condition=condition,kind='community_'+e['kind'],**{k:v for k,v in e.items() if k!='kind'}) for e in world.detector.events)
    for name,content in [('runs',runs),('agents',rows),('agent_communities',connections),('communities',groups),('events',events),('person_comparison',report['person_comparison'])]:
        write_csv(folder/(name+'.csv'),content)
    (folder/'snapshots.json').write_text(json.dumps(dict(run_id=run_id,**data),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return str(folder)
