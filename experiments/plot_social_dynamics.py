"""Plot the recorded CSVs; never reruns or selects simulations."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

base=Path(__file__).resolve().parents[1]/'docs/experiments/social_dynamics_v3'
def read(name):
    with (base/name).open(encoding='utf-8-sig') as f:
        return {(int(r['seed']),r['action']):r for r in csv.DictReader(f) if r['mode']=='adaptive'}
one=read('comparisons.csv');many=read('repeated/comparisons.csv')
seeds=sorted({seed for seed,_ in one})
fig,axes=plt.subplots(1,3,figsize=(11,4),sharey=True)
for ax,action,title in zip(axes,['help','harm','gossip'],['Cooperation','Attack','Gossip']):
    x=np.arange(len(seeds))
    for seed in seeds:
        assert one[seed,action]['baseline_digest']==many[seed,action]['baseline_digest']
    series=[('No intervention',[int(one[s,action]['baseline_ego_degree']) for s in seeds],'#8993a5'),
            ('One action',[int(one[s,action]['final_ego_degree']) for s in seeds],'#359da4'),
            ('Ten actions',[int(many[s,action]['final_ego_degree']) for s in seeds],'#db9e43')]
    for i,(label,values,color) in enumerate(series):ax.bar(x+(i-1)*.24,values,width=.23,label=label,color=color)
    ax.set_xticks(x,labels=[str(s) for s in seeds]);ax.set_xlabel('Seed');ax.set_title(title);ax.set_ylim(0,6)
    ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
axes[0].set_ylabel('Final degree of person 1')
axes[1].legend(loc='upper center',bbox_to_anchor=(.5,-.25),ncol=3,frameon=False)
fig.suptitle('Adaptive model: fixed observation horizon, paired controls')
fig.text(.5,.02,'40 people; 20 warmup steps; 80 observation steps. Three seeds, descriptive results only.',ha='center',fontsize=9)
fig.subplots_adjust(left=.07,right=.99,bottom=.28,top=.81,wspace=.13)
fig.savefig(base/'degree_comparison.png',dpi=160)
print(base/'degree_comparison.png')
