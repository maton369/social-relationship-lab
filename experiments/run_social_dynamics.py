"""Reproducible paired experiments; records outcomes without selecting seeds by result."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/('.deps/windows-cp311' if sys.platform=='win32' else 'vendor')))
from model import Simulation
from social_dynamics import MODES


def digest(world):
    h=hashlib.sha256()
    for a in [world.x,world.a,world.social.trust,world.social.experiences,world.social.remaining,*world.traits.values()]:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def execute(seed,mode,action,warmup,steps,repetitions=1,interval=1):
    s=Simulation(40,seed=seed,settings=MODES[mode])
    initial=digest(s.world)
    for _ in range(warmup):s.step(enforce_limit=False)
    assert digest(s.world)==digest(s.base),'Paired worlds diverged without intervention'
    intervention=digest(s.world)
    actor,subject=0,1
    before=s.world.a.copy();before_x=s.world.x.copy()
    def act():
        return s.gossip_to_neighbors(actor,subject,1.) if action=='gossip' else s.act_to_neighbors(action,actor,1.)
    people=act()
    # Legacy actions are immediate; budgeted actions execute at the next tick.
    if s.p['budget_enabled']:s.step(enforce_limit=False)
    immediate_degree=int(s.world.a[actor].sum())
    immediate_x=s.world.x.copy()
    while s.iteration<warmup+steps:
        offset=s.iteration-warmup
        if offset>0 and offset%interval==0 and offset//interval<repetitions:act()
        s.step(enforce_limit=False)
    final=s.history[-1]
    relevant=[e for e in s.world.timeline if e['step']>=warmup]
    direct_cuts=[e for e in relevant if e['kind']=='tie_cut' and (e.get('trigger') or {}).get('kind')=='direct_action']
    rumors=[e for e in s.world.events if e['kind']=='gossip']
    rows=dict(seed=seed,mode=mode,action=action,warmup=warmup,steps=steps,repetitions=repetitions,interval=interval,
        model_version='3.0',initial_digest=initial,intervention_digest=intervention,
        recipients=len(people),initial_ego_degree=int(before[actor].sum()),
        immediate_ego_degree=immediate_degree,final_ego_degree=int(s.world.a[actor].sum()),
        baseline_ego_degree=int(s.base.a[actor].sum()),direct_cuts=len(direct_cuts),
        liking_difference=final['difference'],tie_difference=final['tie_difference'],
        vi_bits=final['vi_bits'],trust_difference=final['trust_difference'],
        final_ties=int(s.world.a.sum()//2),baseline_ties=int(s.base.a.sum()//2),
        final_isolated=int((s.world.a.sum(axis=1)==0).sum()),
        baseline_isolated=int((s.base.a.sum(axis=1)==0).sum()),
        target_liking_before=float(np.delete(before_x[:,subject],subject).mean()),
        target_liking_immediate=float(np.delete(immediate_x[:,subject],subject).mean()),
        target_liking_difference=float(np.delete(s.world.x[:,subject]-s.base.x[:,subject],subject).mean()),
        gossip_reach=max([int(e['seen'].sum())-1 for e in rumors] or [0]),
        accepted_exchanges=sum(e['kind']=='social_invitation' and e['outcome']=='accepted' for e in relevant),
        rejected_exchanges=sum(e['kind']=='social_invitation' and e['outcome']=='rejected' for e in relevant),
        status=s.status,observation_end={'absorbed':'absorbing','stable':'observed_stable'}.get(s.status,'not_converged'),
        final_digest=digest(s.world),baseline_digest=digest(s.base))
    return rows,s


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',default='23,30,42')
    p.add_argument('--modes',default=','.join(MODES))
    p.add_argument('--warmup',type=int,default=20)
    p.add_argument('--steps',type=int,default=80)
    p.add_argument('--repetitions',type=int,default=1)
    p.add_argument('--interval',type=int,default=1)
    p.add_argument('--no-snapshots',action='store_true')
    p.add_argument('--output',type=Path,default=ROOT/'docs/experiments/social_dynamics_v3')
    args=p.parse_args()
    if args.warmup<0 or args.steps<1:p.error('warmup >= 0 and steps >= 1 are required')
    if args.repetitions<1 or args.interval<1 or (args.repetitions-1)*args.interval>=args.steps:p.error('Invalid repetition schedule')
    modes=args.modes.split(',');seeds=[int(v) for v in args.seeds.split(',')]
    if any(m not in MODES for m in modes):p.error('Unknown mode')
    args.output.mkdir(parents=True,exist_ok=True)
    metadata=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,
        platform=platform.system(),numpy=np.__version__,seeds=seeds,modes=modes,
        warmup=args.warmup,steps=args.steps,n=40,actor=1,gossip_subject=2,strength=1.,
        repetitions=args.repetitions,interval=args.interval,snapshots=not args.no_snapshots,
        note='Descriptive simulations, not empirical human predictions. Mechanisms differ during warmup.',
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['model.py','social_dynamics.py','community.py','experiments/run_social_dynamics.py']})
    (args.output/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    rows=[]
    for seed in seeds:
        for mode in modes:
            for action in ['help','harm','gossip']:
                row,s=execute(seed,mode,action,args.warmup,args.steps,args.repetitions,args.interval);rows.append(row)
                with (args.output/'comparisons.csv').open('w',encoding='utf-8-sig',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                if not args.no_snapshots and seed==seeds[0] and (mode=='adaptive' or (mode=='legacy' and action=='harm')):
                    with gzip.open(args.output/f'seed{seed}_{mode}_{action}.json.gz','wt',encoding='utf-8') as f:
                        json.dump(s.snapshot(),f,ensure_ascii=False,allow_nan=False)
                print(f'{seed} {mode} {action}: ego {row["initial_ego_degree"]}->{row["immediate_ego_degree"]}->{row["final_ego_degree"]}; edge difference {row["tie_difference"]}',flush=True)
    sample=rows[-2]
    rerun,_=execute(sample['seed'],sample['mode'],sample['action'],args.warmup,args.steps,args.repetitions,args.interval)
    assert rerun==sample,'Reproducibility check failed'
    (args.output/'verification.json').write_text(json.dumps(dict(
        paired_state_equality='checked in every run',
        replay=dict(seed=sample['seed'],mode=sample['mode'],action=sample['action'],exact_match=True),
        runs=len(rows)),indent=2),encoding='utf-8')
    lines=['# 自律交流モデル：数値実験記録','',
        f'40人、seeds={seeds}、{args.warmup}時刻の準備後、{args.interval}時刻間隔で{args.repetitions}回の操作を試み、{args.steps}時刻追跡。',
        '人物1は協力・攻撃を全接続者へ、噂は人物2について全接続者へ話す。',
        '各試行の行動あり／なしは介入直前までX・A・信頼・属性・時間残量が完全一致する。',
        'モード間では準備期間から規則が異なるため、介入時のネットワークは同一とは限らない。',
        '3シードの記述的比較であり、母集団の統計的結論ではない。','',
        '| モード | 行動 | 平均の直接切断数 | 平均の最終関係差 | 平均の最終好感度差 | 平均の噂到達人数 |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for mode in modes:
        for action in ['help','harm','gossip']:
            group=[r for r in rows if r['mode']==mode and r['action']==action]
            avg=lambda k:float(np.mean([r[k] for r in group]))
            lines.append(f'| {mode} | {action} | {avg("direct_cuts"):.2f} | {avg("tie_difference"):.2f} | {avg("liking_difference"):.5f} | {avg("gossip_reach"):.2f} |')
    lines+=['','関係差は行動あり／なしで異なる無向辺の本数。大きいほど良いという指標ではない。',
            'comparisons.csvが全試行、metadata.jsonが条件・ソースハッシュ、verification.jsonが再現確認。',
            '圧縮JSONには選択した試行の全時刻X/A/信頼、人物分析、情報・交流・関係変化の履歴を保存。' if not args.no_snapshots else 'この追加条件はCSVの全試行指標とメタデータを保存（全状態スナップショットなし）。',
            '結末を選別するためのシード探索や、分裂・合流を強制する処理は行っていない。']
    (args.output/'results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
