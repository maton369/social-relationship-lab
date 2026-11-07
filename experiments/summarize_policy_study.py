"""Summarize every run, keeping seeds (not people) as the resampling unit."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
METRICS = ('ego_degree','ego_in_liking','ego_in_trust','ties','isolates','negative_liking','exchanges','subject_liking')
LABELS = dict(none='行動なし', help_once='全員へ協力1回',help_burst='全員へ協力5連続',
              help_spaced='全員へ協力5回・間隔4',help_weak='弱い関係の1人へ協力5回',
              help_strong='高信頼の1人へ協力5回',help_new='未接続の1人へ協力5回',
              harm_once='全員へ攻撃1回',harm_burst='全員へ攻撃5連続',
              gossip_burst='有力な知人の悪い噂5連続',repair='攻撃1回後に協力4回')


def read(path):
    rows = list(csv.DictReader(path.open(encoding='utf-8-sig')))
    numeric = [k for k in rows[0] if k.startswith(('delta_','final_','baseline_','compare_','initial_')) and not k.endswith('digest')]
    numeric += ['density','seed','third_party_edge_changes','other_people_losing_degree','ambiguous_people','effective_direct_strength']
    for r in rows:
        for k in numeric:
            r[k] = float(r[k])
    return rows


def summarize(rows):
    keys=sorted({(r['trust_condition'],r['density'],r['policy'],r['split']) for r in rows})
    summary=[]
    for trust,density,policy,split in keys:
        group=[r for r in rows if (r['trust_condition'],r['density'],r['policy'],r['split'])==(trust,density,policy,split)]
        d=dict(trust_condition=trust,density=density,policy=policy,split=split,n_seeds=len(group))
        for metric in METRICS:
            a=np.array([r['delta_'+metric] for r in group])
            d['mean_delta_'+metric]=float(a.mean())
        d['degree_better']=sum(r['delta_ego_degree']>0 for r in group)
        d['degree_worse']=sum(r['delta_ego_degree']<0 for r in group)
        d['degree_equal']=len(group)-d['degree_better']-d['degree_worse']
        d['mean_gossip_reach']=float(np.mean([r['final_gossip_unique_reach'] for r in group]))
        d['mean_edge_changes']=float(np.mean([r['compare_tie_difference'] for r in group]))
        summary.append(d)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'docs/experiments/conditions-and-policies')
    args=p.parse_args();out=args.input
    rows=read(out/'runs.csv');summary=summarize(rows)
    with (out/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,list(summary[0]));w.writeheader();w.writerows(summary)
    natural=[r for r in rows if r['trust_condition']=='natural']
    policies=list(dict.fromkeys(r['policy'] for r in natural))
    rng=np.random.default_rng(20261107)
    estimates=[]
    for policy in policies:
        g=[r for r in natural if r['policy']==policy]
        seeds=sorted({r['seed'] for r in g})
        d=dict(policy=policy,n_seeds=len(seeds),n_conditions=len(g))
        for metric in METRICS:
            a=np.array([np.mean([r['delta_'+metric] for r in g if r['seed']==s]) for s in seeds])
            samples=a[rng.integers(0,len(a),(4000,len(a)))].mean(1)
            lo,hi=np.quantile(samples,[.025,.975])
            d[metric]=dict(mean=float(a.mean()),seed_bootstrap_95=[float(lo),float(hi)])
        d['degree_better']=sum(r['delta_ego_degree']>0 for r in g)
        d['degree_worse']=sum(r['delta_ego_degree']<0 for r in g)
        d['degree_equal']=len(g)-d['degree_better']-d['degree_worse']
        d['incoming_liking_worse']=sum(r['delta_ego_in_liking'] < -1e-9 for r in g)
        estimates.append(d)
    (out/'estimates.json').write_text(json.dumps(estimates,indent=2),encoding='utf-8')
    pairwise=[]
    for first,second in [('help_spaced','help_burst'),('help_weak','help_strong'),('help_new','help_spaced'),('repair','help_spaced')]:
        for split in ('discovery','validation'):
            a={(r['seed'],r['density']):r for r in natural if r['policy']==first and r['split']==split}
            b={(r['seed'],r['density']):r for r in natural if r['policy']==second and r['split']==split}
            keys=sorted(a.keys() & b.keys())
            if not keys:continue
            result=dict(first=first,second=second,split=split,n_conditions=len(keys))
            for metric in ('ego_degree','ego_in_liking','ego_in_trust','ties','isolates'):
                diff=np.array([a[k]['final_'+metric]-b[k]['final_'+metric] for k in keys])
                result[metric]=dict(mean=float(diff.mean()),positive=int((diff>1e-9).sum()),
                    zero=int((abs(diff)<=1e-9).sum()),negative=int((diff < -1e-9).sum()))
            pairwise.append(result)
    (out/'pairwise.json').write_text(json.dumps(pairwise,indent=2),encoding='utf-8')
    # All conditions enter the counts; cases below are descriptive counterexamples,
    # not evidence for their population prevalence or a chosen best seed.
    predicates={
        'help_can_reduce_ego_degree':lambda r:r['policy'] in ('help_once','help_burst','help_spaced') and r['delta_ego_degree']<0,
        'harm_can_increase_ego_degree':lambda r:r['policy'] in ('harm_once','harm_burst') and r['delta_ego_degree']>0,
        'gossip_large_reach_no_edge_difference':lambda r:r['policy']=='gossip_burst' and r['final_gossip_unique_reach']>=20 and r['compare_tie_difference']==0,
        'gossip_subject_liking_increases_later':lambda r:r['policy']=='gossip_burst' and r['delta_subject_liking']>1e-9,
        'help_can_increase_isolates':lambda r:r['policy'] in ('help_once','help_burst','help_spaced') and r['delta_isolates']>0,
        'help_can_reduce_incoming_trust':lambda r:r['policy'] in ('help_once','help_burst','help_spaced') and r['delta_ego_in_trust'] < -1e-9,
        'help_more_ego_ties_fewer_global_ties':lambda r:r['policy'] in ('help_once','help_burst','help_spaced') and r['delta_ego_degree']>0 and r['delta_ties']<0,
    }
    findings={}
    for name,pred in predicates.items():
        cases=[r for r in natural if pred(r)]
        findings[name]=dict(count=len(cases),cases=[dict(seed=int(r['seed']),density=r['density'],policy=r['policy'],
            degree_delta=r['delta_ego_degree'],liking_delta=r['delta_ego_in_liking'],
            trust_delta=r['delta_ego_in_trust'],
            isolate_delta=r['delta_isolates'],subject_liking_delta=r['delta_subject_liking'],
            gossip_reach=r['final_gossip_unique_reach'],edge_changes=r['compare_tie_difference']) for r in cases])
    (out/'counterexamples.json').write_text(json.dumps(findings,indent=2),encoding='utf-8')
    lines=['# 初期条件と行動方針の全条件集計','',
           '各値は行動あり − 同一初期状態の行動なし。Δ関係数は人物1の最終関係数。',
           '勝／同／負はその差の正／ゼロ／負を数えたもの。良好な人間関係の総合順位ではない。',
           'discovery／validationは別のシード集合。閾値・行動方針は結果を見る前に固定。','',
           '| 初期信頼 | 初期密度 | シード群 | 方針 | n | Δ関係数 | 勝／同／負 | Δ受信好感度 | Δ受信信頼 | Δ全体関係 | Δ孤立者 |',
           '| --- | ---: | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |']
    for d in summary:
        lines.append(f'| {d["trust_condition"]} | {d["density"]:.2f} | {d["split"]} | {LABELS[d["policy"]]} | {d["n_seeds"]} | {d["mean_delta_ego_degree"]:+.2f} | {d["degree_better"]}／{d["degree_equal"]}／{d["degree_worse"]} | {d["mean_delta_ego_in_liking"]:+.4f} | {d["mean_delta_ego_in_trust"]:+.4f} | {d["mean_delta_ties"]:+.2f} | {d["mean_delta_isolates"]:+.2f} |')
    (out/'all-conditions.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    shown=[p for p in policies if p!='none']
    fig,axes=plt.subplots(1,3,figsize=(13,5),sharey=True)
    for ax,density in zip(axes,sorted({r['density'] for r in natural})):
        for y,policy in enumerate(shown):
            g=[r for r in natural if r['density']==density and r['policy']==policy]
            vals=np.array([r['delta_ego_degree'] for r in g])
            jitter=np.linspace(-.16,.16,len(g))
            ax.scatter(vals,y+jitter,s=22,alpha=.6,color='#426ba5')
            ax.scatter([vals.mean()],[y],marker='D',color='#bf4b30',s=35)
        ax.axvline(0,color='gray',lw=1)
        ax.set_title(f'Initial density {density:.2f}');ax.set_xlabel('Ego degree: action minus control')
        ax.set_yticks(range(len(shown)),shown);ax.grid(axis='x',alpha=.2)
    axes[0].invert_yaxis()
    fig.suptitle('All predeclared natural-trust conditions; dots = seeds, diamond = mean')
    fig.tight_layout();fig.savefig(out/'degree_outcomes.png',dpi=160);plt.close(fig)
    case=out/'cases/s2_d0.1_help_spaced_t240-series.json'
    if case.exists():
        series=json.loads(case.read_text(encoding='utf-8'))
        fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True)
        t=[r['step'] for r in series]
        for ax,field,control,label in [(axes[0],'degree','baseline_degree','Ego degree'),
                                      (axes[1],'incoming_liking','baseline_liking','Mean incoming liking')]:
            ax.plot(t,[r[control] for r in series],label='No intervention',color='#6e7781')
            ax.plot(t,[r[field] for r in series],label='Help neighbors, five spaced rounds',color='#267969')
            ax.set_ylabel(label);ax.grid(alpha=.2)
            for step in (1,5,9,13,17):ax.axvline(step,color='#d5a241',alpha=.25)
        axes[0].legend();axes[-1].set_xlabel('Steps since intervention start')
        axes[0].set_title('Seed 2, density 0.10: higher liking, one fewer tie at step 240')
        fig.tight_layout();fig.savefig(out/'horizon_counterexample.png',dpi=160);plt.close(fig)
    print(json.dumps(dict(runs=len(rows),counterexample_counts={k:v['count'] for k,v in findings.items()}),indent=2))


if __name__=='__main__':main()
