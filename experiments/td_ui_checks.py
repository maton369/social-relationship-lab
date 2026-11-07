"""Run inside a disposable TouchDesigner validation session via MCP/Textport.

This resets the validation simulation and uses actual virtual mouse clicks.
It does not save or overwrite a .toe file.
"""
import hashlib
import json
import time
from pathlib import Path
import numpy as np

c=op('/social_relationship_lab')
if c is None:raise RuntimeError('Validation component not found')
r=c.op('runtime').module
base=Path(c.par.Basefolder.eval())
report=dict(project=project.name,build=str(app.build),passed=False,
    interaction='PanelCOMP.interactMouse virtual left/right clicks; actual Panel Execute callbacks',
    automatic_clock='held during deterministic button tests; steps driven by the step button',
    source_sha256={f:hashlib.sha256((base/f).read_bytes()).hexdigest() for f in ['runtime.py','model.py','social_dynamics.py']},
    scenarios=[],issues_fixed=['Right-click UV tracking was disabled; enabled on graph and root panels.'])
try:
    for mode in ['legacy','history','budget','adaptive']:
        for action in ['help','harm','gossip']:
            c.par.Running=False;c.par.Dynamics=mode;c.par.Seed=23;c.par.Strength=1.;c.par.Population=40
            c.op('button_reset').interactMouse(.5,.5,leftClick=1)
            r.last_tick=time.monotonic()+3600
            s=r.sim
            assert s.iteration==0
            assert np.array_equal(s.world.x,s.base.x)
            c.op('button_'+action).interactMouse(.5,.5,leftClick=1)
            queued=len(s.world.scheduled_actions)
            assert bool(c.par.Running)
            if mode=='legacy' and action=='help':
                c.op('button_run').interactMouse(.5,.5,leftClick=1)
                assert not bool(c.par.Running)
                c.op('button_run').interactMouse(.5,.5,leftClick=1)
                assert bool(c.par.Running)
            c.par.Running=False
            for _ in range(5):c.op('button_step').interactMouse(.5,.5,leftClick=1)
            assert s.iteration==5
            assert s.world.events and s.world.events[0]['kind']==action
            assert not c.op('diagnostics').text,c.op('diagnostics').text
            assert not c.errors(recurse=True)
            report['scenarios'].append(dict(mode=mode,action=action,queued_before_step=queued,step=s.iteration,
                events=len(s.world.events),strengths=[e['strength'] for e in s.world.events],
                ego_degree=int(s.world.a[0].sum()),edge_difference=s.history[-1]['tie_difference'],
                sidebar=str(c.par.Sidebar),errors=c.errors(recurse=True),diagnostics=c.op('diagnostics').text))
    for index,right in [(3,False),(2,True),(0,False)]:
        x,y=r.view.pos[index]
        c.op('graph_panel').interactMouse(float(x/r.view.w),float(1-y/r.view.h),
            **({'rightClick':1} if right else {'leftClick':1}))
        assert int(c.par.Target if right else c.par.Actor)==index+1
    report.update(graph_selection='passed',start_pause='passed',reset_and_step='passed')
    c.par.Target=2;c.par.Sidebar='gossip';c.par.Display='information';r.refresh()
    assert '信用 / 要求変化' in c.op('details').par.text.eval()
    c.op('button_export').interactMouse(.5,.5,leftClick=1)
    folder=Path(c.fetch('last_export'))
    data=json.loads((folder/'snapshots.json').read_text(encoding='utf-8'))
    assert data['model_version']=='3.0'
    assert 'trust' in data and 'baseline_trust' in data
    report['export']=dict(passed=True,path=str(folder.relative_to(base)))
    report['passed']=True
finally:
    c.par.Running=False;r.last_tick=0.
    output=base/'docs/experiments/social_dynamics/ui_checks.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('UI checks passed:',report['passed'],'scenarios:',len(report['scenarios']))
