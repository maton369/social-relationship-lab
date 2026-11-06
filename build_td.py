"""Execute inside the EXISTING TouchDesigner project. Never loads/saves a TOE.

Creates only /social_relationship_lab_v2_analysis and exports a TOX requiring vendor/.
Refuses to overwrite an existing component. Model code is embedded in DATs.
"""
import json
import traceback
from pathlib import Path
import td
root = td.op('/')
op = td.op
project = td.project
ui = td.ui

BASE = Path(__file__).resolve().parent
REPORT = BASE/'analysis_build_report.json'


def build():
    existing=[o.path for o in root.children]
    project_before=(project.name,project.folder,ui.performMode)
    if op('/social_relationship_lab_v2_analysis'):
        raise RuntimeError('/social_relationship_lab_v2_analysis already exists; no component was replaced.')
    b=root.create(td.containerCOMP,'social_relationship_lab_v2_analysis')
    b.par.w=1280;b.par.h=820
    b.par.bgcolorr=.047;b.par.bgcolorg=.078;b.par.bgcolorb=.122;b.par.bgalpha=1
    b.nodeX=1200;b.nodeY=-800
    b.store('basefolder',str(BASE))
    page=b.appendCustomPage('Simulation')
    def integer(name,value,low,high,label):
        p=page.appendInt(name,label=label)[0];p.val=value
        p.min=low;p.max=high;p.clampMin=True;p.clampMax=True
        p.normMin=low;p.normMax=high
        return p
    page.appendStr('Basefolder',label='依存パッケージのフォルダ')[0].val=str(BASE)
    integer('Population',40,4,80,'人数（初期化で反映）')
    integer('Seed',23,0,100000,'乱数シード（初期化で反映）')
    page.appendToggle('Running',label='実行')[0].val=False
    integer('Speed',1,1,10,'1回の更新ステップ数')
    integer('Actor',1,1,80,'行動する人')
    integer('Target',2,1,80,'対象の人')
    def floating(name,value,low,high,label):
        p=page.appendFloat(name,label=label)[0];p.val=value
        p.min=low;p.max=high;p.normMin=low;p.normMax=high;p.clampMin=True;p.clampMax=True
    floating('Strength',.8,0,1,'行動の強さ')
    floating('Formation',.55,.01,1,'選択人物：関係成立閾値')
    floating('Cut',.25,-1,.99,'選択人物：関係切断閾値')
    floating('Receive',.65,0,1,'選択人物：影響感受性')
    floating('Spread',.55,0,1,'選択人物：情報拡散傾向')
    for name,labels,names in [('Display',['関係','好感度','情報','行動あり／なし','属性分布'],['network','affinity','information','comparison','distribution']),('Sidebar',['人物','集団','分析','比較','履歴','分布'],['person','community','analysis','compare','history','distribution'])]:
        m=page.appendMenu(name)[0];m.menuNames=names;m.menuLabels=labels;m.val=names[0]
    page=b.appendCustomPage('Model')
    for name,value,lo,hi,label in [('Density',.1,0,1,'初期関係密度（初期化で反映）'),('Gamma',.25,.01,1,'CPM密度基準'),('Qzero',.03,0,1,'基本接触確率'),('Qtri',.1,0,1,'共通友人の接触増分'),('Pmax',.7,0,1,'伝達確率係数'),('Etav',.5,0,1,'当事者への効果'),('Etao',.4,0,1,'第三者への効果'),('Etar',.3,0,1,'噂の効果'),('Omega',.65,0,1,'対象への評価の重み'),('Tolerance',.005,0,.1,'好感度安定の許容値')]:
        floating(name,value,lo,hi,label)
    integer('Witnesses',2,0,10,'初期目撃者の上限')
    integer('Limit',100,10,1000,'バッチ計算上限（画面は手動停止）')
    integer('Window',10,1,50,'安定確認窓')

    page=b.appendCustomPage('Analysis')
    integer('Communitymin',3,3,5,'主要集団の最小人数（初期化）')
    integer('Hubsize',4,4,12,'ハブ判定の最小人数（初期化）')
    integer('Hubdegree',3,1,20,'ハブの最小内部次数（初期化）')
    floating('Hubratio',.60,0,1,'ハブの最小内部接続率（初期化）')
    floating('Highliking',.50,-1,1,'高好感度の閾値（初期化）')

    for name in ('community','model','view','export_analysis','runtime'):
        d=b.create(td.textDAT if name!='runtime' else td.executeDAT,name)
        d.text=(BASE/(name+'.py')).read_text(encoding='utf-8')
        if name=='runtime':
            d.par.framestart=False;d.par.start=False
    b.create(td.textDAT,'diagnostics')
    b.create(td.tableDAT,'people')
    b.create(td.tableDAT,'appraisals')

    def text(name,content,w,h,size=18,bg=(.047,.078,.122)):
        t=b.create(td.textTOP,name)
        t.par.text=content;t.par.font='Hiragino Sans'
        t.par.typeface='W4'
        t.par.fontsizex=size;t.par.fontsizey=size
        t.par.fontsizexunit='pixels';t.par.fontsizeyunit='pixels'
        t.par.outputresolution='custom';t.par.resolutionw=w;t.par.resolutionh=h
        t.par.bgalpha=1
        t.par.bgcolorr=bg[0];t.par.bgcolorg=bg[1];t.par.bgcolorb=bg[2]
        t.par.fontcolorr=.85;t.par.fontcolorg=.90;t.par.fontcolorb=.94
        return t
    def panel(name,x,y,w,h,top):
        c=b.create(td.containerCOMP,name)
        c.par.x=x;c.par.y=y;c.par.w=w;c.par.h=h
        if top is not None:c.par.top.expr="parent().op(%r).path"%top.name
        return c
    panel('title_panel',0,764,1280,56,text('title','RELATIONSHIP LAB  /  人物・コミュニティ分析',1280,56,25))
    panel('stats_panel',0,720,1280,44,text('stats','準備中',1280,44,18,(.065,.12,.16)))
    cb=b.create(td.textDAT,'network_callbacks')
    cb.text="def onCook(scriptOp):\n    scriptOp.copyNumpyArray(parent().op('runtime').module.image[::-1].copy())\n"
    network=b.create(td.scriptTOP,'network');network.par.callbacks.expr="parent().op('network_callbacks').path"
    panel('graph_panel',16,156,900,556,network)
    panel('detail_panel',928,156,336,556,text('details','',336,556,14))
    panel('event_panel',16,102,1248,46,text('event_log','',1248,46,14))
    panel('foot_panel',0,0,1280,44,text('footer','',1280,44,13))
    for i,(name,label) in enumerate([('run','実行 / 続ける'),('step','1ステップ'),('reset','同じ初期値'),('new','乱数を変更'),('help','協力する'),('harm','攻撃する'),('gossip','悪い噂'),('view','表示：関係'),('group','詳細：人物'),('analyze','分析'),('export','記録を保存'),('settings','設定')]):
        top=text(name+'_label',label,100,42,14,(.08,.21,.25) if name in ('help','run') else (.09,.13,.19))
        c=panel('button_'+name,16+i*104,52,100,42,top)
        events=b.create('panelexecuteDAT','click_'+name)
        events.par.panels.expr="parent().op(%r).path"%c.name;events.par.panelvalue='lselect'
        events.par.offtoon=True;events.par.ontooff=False;events.par.valuechange=False
        events.text="def onOffToOn(panelValue):\n    parent().op('runtime').module.command(%r)\n"%name
    events=b.create('panelexecuteDAT','graph_click')
    events.par.panels.expr="parent().op('graph_panel').path";events.par.panelvalue='lselect rselect'
    events.par.offtoon=True;events.par.ontooff=False;events.par.valuechange=False
    events.text="def onOffToOn(panelValue):\n    parent().op('runtime').module.click_graph(panelValue.name == 'rselect')\n"
    changes=b.create('parameterexecuteDAT','settings_changed')
    changes.par.op.expr="parent().path"
    changes.par.pars='Actor Target Formation Cut Receive Spread Display Sidebar Gamma Qzero Qtri Pmax Etav Etao Etar Omega Limit Window Tolerance Witnesses'
    changes.par.valuechange=True
    changes.text="def onValueChange(par, prev):\n    parent().op('runtime').module.changed(par)\n"
    for i,n in enumerate(b.children):n.nodeX=(i%8)*180;n.nodeY=-(i//8)*130
    b.op('runtime').module.init()
    b.op('runtime').par.start=True
    b.op('runtime').par.framestart=True
    b.op('network').cook(force=True)
    capture=b.create(td.opviewerTOP,'panel_capture')
    capture.par.opviewer.expr="parent().path"
    capture.par.outputresolution='custom'
    capture.par.resolutionw=1280;capture.par.resolutionh=820
    b.save(str(BASE/'Social_Relationship_Lab_Analysis.tox'))
    after=(project.name,project.folder,ui.performMode)
    assert after==project_before,'Unexpected change to current project identity or perform mode'
    assert all(op(path) is not None for path in existing),'An existing root operator is missing'
    report={'ok':True,'component':b.path,'saved':str(BASE/'Social_Relationship_Lab_Analysis.tox'),
            'project_before':project_before,'project_after':after,'existing_roots':existing,
            'running':bool(b.par.Running),'errors':b.errors(recurse=True),'warnings':b.warnings(recurse=True)}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    b.openViewer()
    print('Social Relationship Lab created; shark project retained:',project.name)


try:
    build()
except Exception:
    REPORT.write_text(json.dumps({'ok':False,'error':traceback.format_exc()},ensure_ascii=False,indent=2),encoding='utf-8')
    raise
