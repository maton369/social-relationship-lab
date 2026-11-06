"""TouchDesigner adapter. All simulation state belongs to the owning COMP."""
import sys,time,json,csv,traceback,os
from pathlib import Path
import numpy as np
import unicodedata

sim=None
view=None
busy=False
last_tick=0.
image=np.zeros((556,900,4),np.float32)


def owner():return me.parent()


def wrap_panel(text,width=44):
    lines=[]
    for line in text.split('\n'):
        current='';used=0
        for char in line:
            size=2 if unicodedata.east_asian_width(char) in ('W','F') else 1
            if used+size>width:lines.append(current);current='';used=0
            current+=char;used+=size
        lines.append(current)
    return '\n'.join(lines)


def init():
    global sim,view
    p=owner()
    candidates=[os.environ.get('SOCIAL_LAB_HOME',''), str(project.folder), str(p.par.Basefolder)]
    base=next((Path(v) for v in candidates if v and (Path(v)/'model.py').is_file()), None)
    if base is None:raise RuntimeError('プロジェクト一式を展開し、Basefolder を配置先へ設定してください。')
    p.par.Basefolder=str(base)
    packages=Path(os.environ.get('SOCIAL_LAB_PACKAGES') or
                  str(base/('.deps/windows-cp311' if sys.platform=='win32' else 'vendor')))
    vendor=str(packages)
    if not (packages/'leidenalg').is_dir():raise RuntimeError('Windows は start_windows.cmd で環境構築してください。依存先: '+vendor)
    if vendor not in sys.path:sys.path.insert(0,vendor)
    if sys.platform=='win32':
        for node in p.children:
            if node.OPType=='textTOP':
                node.par.font='Yu Gothic UI'
                node.par.typeface='Regular'
    settings={key:float(getattr(p.par,par)) for key,par in [('density','Density'),('q0','Qzero'),('qtri','Qtri'),
        ('pmax','Pmax'),('eta_v','Etav'),('eta_o','Etao'),('eta_r','Etar'),('omega','Omega'),('gamma','Gamma'),('tolerance','Tolerance')]}
    settings.update(witnesses=int(p.par.Witnesses),window=int(p.par.Window),limit=int(p.par.Limit),
        community_min=int(p.par.Communitymin),hub_min_size=int(p.par.Hubsize),hub_degree=int(p.par.Hubdegree),hub_ratio=float(p.par.Hubratio),high_liking=float(p.par.Highliking))
    sim=p.op('model').module.Simulation(int(p.par.Population),int(p.par.Seed),settings,p.op('community').module)
    view=p.op('view').module.View(sim.n,sim.seed)
    for _ in range(100):view.layout(sim,pinned=int(p.par.Actor)-1)
    p.par.Running=False;p.par.Actor.max=sim.n;p.par.Target.max=sim.n
    p.par.Actor.normMax=sim.n;p.par.Target.normMax=sim.n
    p.par.Target=2
    select(0)
    refresh()


def select(index):
    global busy
    p=owner();i=max(0,min(sim.n-1,int(index)));busy=True
    try:
        p.par.Actor=i+1
        for param,key in [('Formation','form'),('Cut','cut'),('Receive','receive'),('Spread','spread')]:getattr(p.par,param).val=float(sim.world.traits[key][i])
    finally:busy=False


def refresh():
    global image
    p=owner();w=sim.world;d=w.detector
    a=max(0,min(sim.n-1,int(p.par.Actor)-1));t=max(0,min(sim.n-1,int(p.par.Target)-1))
    for _ in range(2):view.layout(sim,pinned=a)
    mode=str(p.par.Display)
    rows=w.role_rows()
    if mode=='comparison':
        base_rows=sim.base.role_rows()
        changed=[i for i,(x,y) in enumerate(zip(rows,base_rows)) if x['roles']!=y['roles'] or x['degree']!=y['degree'] or x['brokerage_disconnected_pairs']!=y['brokerage_disconnected_pairs']]
        image=view.comparison(sim,a,t,changed)
    elif mode=='distribution':image=view.distribution(rows,a)
    else:image=view.image(sim,a,t,mode)
    p.op('network').cook(force=True)
    status={'ready':'準備完了','running':'更新中','stable':'観測上の安定','absorbed':'停止状態を確認','limit':'上限到達・未安定'}.get(sim.status,sim.status)
    status=('実行中' if p.par.Running else '一時停止')+' / '+status
    rows=w.role_rows();isolated=sum(r['isolated'] for r in rows)
    p.op('stats').par.text=f'{status}  |  STEP {sim.iteration:03d}  |  関係 {w.a.sum()//2}  |  主要集団 {sum(len(g)>=sim.p["community_min"] for g in d.groups)} / 二者 {sum(len(g)==2 for g in d.groups)}  |  孤立 {isolated}  |  情報待ち {w.pending}'
    sidebar=str(p.par.Sidebar)
    r=rows[a]
    if sidebar=='person':
        c=r['community'];group='未所属' if c is None else 'C%02d'%c
        ratio='—' if r['internal_ratio'] is None else '%.2f'%r['internal_ratio']
        liking='—' if r['internal_incoming_mean'] is None else '%+.2f'%r['internal_incoming_mean']
        text=(f'人物 {a+1:02d} / {group}\n'+r['roles'][0]+'\n'+'・'.join(r['role_tags'])+'\n\n'
            f'関係 {r["degree"]} / 内部 {r["internal_degree"]}\n内部接続率 {ratio} / 外部 {r["external_degree"]}\n'
            f'接続する主要集団 {r["communities_contacted"]}\n削除で失われる集団間ペア {r["brokerage_disconnected_pairs"]}\n\n'
            f'集団内の受信好感度 {liking}\n全体の受信 {r["incoming_mean"]:+.2f} / 送信 {r["outgoing_mean"]:+.2f}\n'
            f'対象へ {w.x[a,t]:+.2f} / 対象から {w.x[t,a]:+.2f}\n\n'
            f'成立 {r["formation"]:.2f} / 切断 {r["cut"]:.2f}\n感受性 {r["receptivity"]:.2f} / 拡散 {r["spread"]:.2f}\n'
            f'実現伝達 {r["successful_transmissions"]}件 / 相手 {r["unique_people_informed"]}人\n\n'
            f'初期関係 {r["initial_degree"]} → 現在 {r["degree"]}\n成立 {r["formed"]} / 切断 {r["lost"]} / 再成立 {r["ties_reformed"]}\n'+r['isolation_transition']+
            '\n\n左クリック：行動者 / 右：対象\nタグは重複可能。人物の固定的性格ではない。')
    elif sidebar=='community':
        c=r['community']
        groups=sim.measure.community_rows(w.a,d,rows,{k:sim.p[k] for k in sim.measure.ROLE_DEFAULTS})
        group=next((g for g in groups if g['community_id']==c),None)
        if group is None:
            contacts=[f'C{k}: {v}本' for k,v in r['community_connections'].items() if v]
            text=f'人物 {a+1:02d} / '+r['roles'][0]+'\n\n主要コミュニティへの接続\n'+'\n'.join(contacts or ['なし'])+'\n\n二者関係は主要集団と別に扱います。'
        else:
            def external(values):return ', '.join('%02d(%d)'%(v['person'],v['ties']) for v in values) or 'なし'
            text=(f'C{c:02d} / {group["size"]}人\n構成員 '+', '.join(map(str,group['members']))+
                f'\n\n内部密度 {group["density"]:.3f} / γ {sim.p["gamma"]:.2f}\n'
                '内部ハブ '+(', '.join(map(str,group['internal_hubs'])) or 'なし')+
                '\n構造的橋渡し '+(', '.join(map(str,group['structural_brokers'])) or 'なし')+
                '\n\n他集団からの外部接続者（本数）\n'+external(group['external_members'])+
                '\n\n未所属からの外部接続者（本数）\n'+external(group['external_unassigned'])+
                '\n\n曖昧な所属 '+str(len(group['ambiguous_members']))+'人\n確定分裂・合流など '+str(len(d.events))+'件\n\n外部接続は接続本数順に表示。')
    elif sidebar=='compare':
        other=sim.base.role_rows()[a]
        text=f'人物 {a+1:02d} / 行動なし → あり\n\n'
        for key,label,fmt in [('degree','関係数','d'),('internal_ratio','内部接続率','.2f'),('incoming_mean','受信好感度','+.2f'),('brokerage_disconnected_pairs','削除時の喪失ペア','d'),('lost','切断数','d')]:
            show=lambda value:'—' if value is None else format(value,fmt)
            text+=label+' '+show(other[key])+' → '+show(r[key])+'\n'
        text+='\n行動なし\n'+'・'.join(other['roles'])+'\n\n行動あり\n'+'・'.join(r['roles'])+'\n\n左右は同一人物・同じ座標。\n赤い輪：役割・次数・橋渡し指標に差。'
    elif sidebar=='history':
        names={'tie_formed':'関係成立','tie_cut':'関係切断','transmission':'情報受信','observation':'直接観測','action':'行動','join':'構造的加入','leave':'構造的離脱','membership_structure_changed':'所属構造の変化','attribute_edit':'属性変更','appraisal_update':'好感度更新'}
        relevant=[e for e in w.timeline if e['kind']!='transmission_attempt' and (e.get('person')==a+1 or e.get('actor')==a+1 or e.get('target')==a+1 or a+1 in e.get('people',[]) or a+1 in e.get('sources',[]))]
        text=f'人物 {a+1:02d} / 履歴（直近14件）\n初期：'+r['initial_roles'][0]+f' / 関係 {r["initial_degree"]}\n\n'
        for e in relevant[-14:]:
            detail=' '+','.join(map(str,e['people'])) if 'people' in e else ' 元 '+','.join(map(str,e['sources'])) if 'sources' in e else ''
            text+=f't={e["step"]:03d} '+names.get(e['kind'],e['kind'])+detail+'\n'
        text+='\n全履歴は events.csv に保存。\n切断時の評価と閾値も記録します。\n更新段階は原因の証明とは区別します。'
    elif sidebar=='distribution':
        text='役割別・全人物の属性分布\n\n列：左から\n1 成立閾値（0〜1）\n2 切断閾値（−1〜1）\n3 感受性（0〜1）\n4 拡散傾向（0〜1）\n\n行：上から\n1 内部ハブ\n2 横断的接続者\n3 構造的橋渡し役\n4 孤立者\n\n一つの点が一人物。金色は選択人物。\n役割を兼ねる人は複数行に表示。\n人数0の行は空欄です。\n\n現在値を描画しています。\n初期属性もCSVに別途保存します。'
    else:
        report=sim.analysis or sim.summary();counts=report['role_attributes'];qc=report.get('quality_check')
        text=('安定確認後の分析' if sim.status in ('absorbed','stable') else '現在時点の分析')+f' / t={sim.iteration}\n\n'
        for key,label in [('hub','内部ハブ'),('multi_community_connector','横断的接続者'),('structural_broker','構造的橋渡し役'),('isolated','孤立者')]:
            v=counts[key];text+=f'{label} {v["n"]}人\n'
            if v['n']:text+=f' 成立 {v["formation"]:.2f} / 切断 {v["cut"]:.2f}\n 感受性 {v["receptivity"]:.2f} / 拡散 {v["spread"]:.2f}\n'
        text+='\n役割の重複を許します。\n'
        if qc:
            text+=qc['interpretation']+'\n'
            if qc['exploratory_p'] is not None:text+=f'探索的 p={qc["exploratory_p"]:.3f} / 無作為化39回\n'
        text+=f'\n将来成立し得る関係 {w.possible_contacts}\n情報の未処理 {w.pending}\n\n一試行の記述的比較です。'
    p.op('details').par.text=wrap_panel(text)
    p.op('run_label').par.text='一時停止' if p.par.Running else '実行 / 再開'
    p.op('group_label').par.text={'person':'詳細：人物','community':'詳細：集団','analysis':'詳細：全体','compare':'詳細：比較','history':'詳細：履歴','distribution':'詳細：分布'}[sidebar]
    p.op('view_label').par.text={'network':'表示：関係','affinity':'表示：好感度','information':'表示：情報','comparison':'表示：比較','distribution':'表示：分布'}[mode]
    events=w.events[-2:]
    names={'help':'協力','harm':'攻撃','gossip':'悪い噂'}
    p.op('event_log').par.text='\n'.join(f't={e["step"]:03d}  {e["actor"]+1:02d} → {e["target"]+1:02d}  {names[e["kind"]]}  到達 {int(e["seen"].sum())}人' for e in events) or '人物と対象を選択 → 協力・攻撃・悪い噂。集団ラベルは社会の更新規則に使いません。'
    if mode=='comparison':p.op('event_log').par.text='左：行動なし / 右：行動あり。同じ人物を同じ座標で描画。赤い輪は役割・次数・削除時の喪失ペアに差がある人物。'
    if mode=='distribution':p.op('event_log').par.text='列：成立閾値 / 切断閾値 / 感受性 / 拡散傾向　行：内部ハブ / 横断的接続者 / 構造的橋渡し役 / 孤立者'
    h=sim.history[-1];scale=max(.001,max(v['difference'] for v in sim.history[-400:]))
    p.op('footer').par.text=f'SEED {sim.seed}  /  好感度差 {h["difference"]:.4f}  /  関係差 {h["tie_difference"]}  /  分割差VI {h["vi_bits"]:.3f} bits  /  下のグラフ 0〜{scale:.4f}'
    table=p.op('people');table.clear()
    keys=['person','community','roles','degree','internal_degree','external_degree','betweenness','formation','cut','receptivity','spread','initial_degree','formed','lost']
    table.appendRow(keys)
    for r in rows:table.appendRow([','.join(r[k]) if isinstance(r[k],list) else r[k] if r[k] is not None else '' for k in keys])
    matrix=p.op('appraisals');matrix.clear();matrix.appendRow(['from/to']+list(range(1,sim.n+1)))
    for i in range(sim.n):matrix.appendRow([i+1]+[round(float(v),5) for v in w.x[i]])


def export():
    p=owner();path=p.op('export_analysis').module.save(sim,Path(str(p.par.Basefolder))/'exports')
    p.store('last_export',path)


def command(name):
    p=owner()
    try:
        if name=='run':
            p.par.Running=not bool(p.par.Running)
            if not p.par.Running:sim.analysis=sim.summary(with_null=True)
        elif name=='step':p.par.Running=False;sim.step(enforce_limit=False)
        elif name in ('reset','new'):
            if name=='new':p.par.Seed=int(p.par.Seed)+1
            init()
        elif name in ('help','harm','gossip'):
            sim.act(name,int(p.par.Actor)-1,int(p.par.Target)-1,float(p.par.Strength));p.par.Running=True
        elif name=='view':
            names=['network','affinity','information','comparison','distribution'];p.par.Display=names[(names.index(str(p.par.Display))+1)%len(names)]
        elif name=='group':
            names=['person','community','analysis','compare','history','distribution'];p.par.Sidebar=names[(names.index(str(p.par.Sidebar))+1)%len(names)]
            if str(p.par.Sidebar)=='compare':p.par.Display='comparison'
            elif str(p.par.Sidebar)=='distribution':p.par.Display='distribution'
            elif str(p.par.Display) in ('comparison','distribution'):p.par.Display='network'
        elif name=='analyze':
            p.par.Running=False;sim.analysis=sim.summary(with_null=True);p.par.Sidebar='analysis'
        elif name=='export':
            if sim.analysis is None:sim.analysis=sim.summary()
            export()
        elif name=='settings':p.openParameters()
        refresh()
    except Exception as e:
        p.par.Running=False;p.op('diagnostics').text=traceback.format_exc();p.op('event_log').par.text=str(e)


def changed(par):
    if busy or sim is None:return
    p=owner();name=par.name
    if name=='Actor':select(int(par)-1);p.par.Sidebar='person'
    elif name in ('Formation','Cut','Receive','Spread'):
        i=int(p.par.Actor)-1
        values=[float(getattr(p.par,k)) for k in ('Formation','Cut','Receive','Spread')]
        old=[sim.world.traits[k][i] for k in ('form','cut','receive','spread')]
        if np.allclose(values,old,atol=1e-7):return
        try:sim.edit_person(i,*values)
        except ValueError as e:p.op('event_log').par.text=str(e);select(i);return
    elif name=='Gamma':
        sim.p['gamma']=float(par)
        for w in (sim.world,sim.base):
            w.p['gamma']=float(par);w.detector.gamma=float(par);w.detector.detect(w.a,w.time,track_events=False);w.c_quiet=0
            w.detector.pending=[]
        sim.analysis=None
        for w in (sim.world,sim.base):
            w.timeline.append(dict(step=w.time,kind='analysis_resolution_change',gamma=float(par)))
            w.capture('analysis_resolution_change')
        sim.record()
    else:
        live={'Qzero':'q0','Qtri':'qtri','Pmax':'pmax','Etav':'eta_v','Etao':'eta_o','Etar':'eta_r','Omega':'omega','Limit':'limit','Window':'window','Tolerance':'tolerance','Witnesses':'witnesses'}
        if name in live:
            key=live[name];v=int(par) if name in ('Limit','Window','Witnesses') else float(par)
            sim.p[key]=v
            for w in (sim.world,sim.base):
                w.p[key]=v;w.timeline.append(dict(step=w.time,kind='parameter_change',parameter=key,value=v))
            sim.analysis=None
    refresh()


def click_graph(right=False):
    p=owner()
    if str(p.par.Display)=='distribution':return
    panel=p.op('graph_panel').panel
    pos=np.array([float(panel.u)*view.w,(1.-float(panel.v))*view.h])
    if str(p.par.Display)=='comparison':pos[0]=(pos[0]%450)*2
    distance=np.linalg.norm(view.pos-pos,axis=1);i=int(distance.argmin())
    if distance[i]>27:return
    if right:p.par.Target=i+1
    else:select(i);p.par.Sidebar='person'
    refresh()


def onStart():init()


def onFrameStart(frame):
    global last_tick
    p=owner()
    try:
        if sim is None:init()
        now=time.monotonic()
        if not p.par.Running or now-last_tick<.2:return
        last_tick=now
        for _ in range(int(p.par.Speed)):
            sim.step(enforce_limit=False)
        refresh()
    except Exception:
        p.par.Running=False;p.op('diagnostics').text=traceback.format_exc()
        p.op('event_log').par.text='エラー：diagnostics DAT を確認してください。'
