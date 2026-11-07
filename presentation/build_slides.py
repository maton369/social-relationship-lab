"""Editable lecture deck built from the project's real screenshots and run records."""
from pathlib import Path
import csv
import json
import shutil
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT/'docs/experiments/conditions-and-policies'
ASSETS = HERE/'assets'
ASSETS.mkdir(parents=True,exist_ok=True)
BG='#0C141F'; PANEL='#142331'; WHITE='#F3F6F9'; MUTED='#B0C0CF'
TEAL='#64D6BE'; GOLD='#F1C371'; CORAL='#F59A99'; GRAY='#8596A7'; BLUE='#8FB4EE'
FONT='Hiragino Sans'
prs=Presentation();prs.slide_width=Inches(13.333333);prs.slide_height=Inches(7.5)
notes=[];timings=[15,35,50,25,65,50,40,20]


def rgb(v):return RGBColor.from_string(v.strip('#'))


def box(s,x,y,w,h,fill=PANEL,line=None,radius=False):
    v=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                         Inches(x), Inches(y), Inches(w), Inches(h))
    v.fill.solid();v.fill.fore_color.rgb=rgb(fill)
    if line:v.line.color.rgb=rgb(line)
    else:v.line.fill.background()
    return v


def text(s,string,x,y,w,h,size=24,color=WHITE,bold=False,align=None,font=FONT):
    v=s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf=v.text_frame;tf.clear();tf.word_wrap=True
    tf.margin_left=0;tf.margin_right=0;tf.margin_top=0;tf.margin_bottom=0
    for i,line in enumerate(string.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text=line;p.font.name=font;p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=rgb(color)
        p.space_after=Pt(5)
        if align is not None:p.alignment=align
    return v


def link(s,string,url,x,y,w,size=12):
    v=text(s,string,x,y,w,.36,size,BLUE)
    for p in v.text_frame.paragraphs:
        for r in p.runs:r.hyperlink.address=url
    return v


def line(s,x1,y1,x2,y2,color=GRAY,width=2):
    v=s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    v.line.color.rgb=rgb(color);v.line.width=Pt(width)
    return v


def circle(s,x,y,d,fill=TEAL,label=None,size=16):
    v=s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    v.fill.solid();v.fill.fore_color.rgb=rgb(fill);v.line.fill.background()
    if label is not None:
        tf=v.text_frame;tf.margin_left=0;tf.margin_right=0;tf.margin_top=0;tf.margin_bottom=0
        tf.vertical_anchor=MSO_ANCHOR.MIDDLE
        p=tf.paragraphs[0];p.text=str(label);p.alignment=PP_ALIGN.CENTER
        p.font.name=FONT;p.font.size=Pt(size);p.font.bold=True;p.font.color.rgb=rgb(BG)
    return v


def slide(title,tag=''):
    s=prs.slides.add_slide(prs.slide_layouts[6]);s.background.fill.solid();s.background.fill.fore_color.rgb=rgb(BG)
    n=len(prs.slides)
    text(s,tag or ('SOCIAL RELATIONSHIP LAB  /  作品発表' if n<=8 else 'SUPPLEMENT  /  質疑用の補足'),.65,.3,11,.3,11,MUTED)
    if title:text(s,title,.65,.85,12.05,.72,30,bold=True)
    text(s,f'{n:02d} / 08' if n<=8 else f'補足 {n-8}',11.7,7.08,.95,.24,10,MUTED,align=PP_ALIGN.RIGHT)
    if n<=8:box(s,.65,7.07,10.6*n/8,.025,TEAL)
    return s


def note(s,title,script,extra=''):
    n=len(prs.slides);duration=timings[n-1] if n<=8 else 0
    elapsed=sum(timings[:n]) if n<=8 else 300
    body=f'{duration}秒 / 累計 {elapsed//60}:{elapsed%60:02d}\n\n{script}' if n<=8 else script
    if extra:body+='\n\n【操作・出典・留意点】\n'+extra
    s.notes_slide.notes_text_frame.text=body
    notes.append(dict(number=n,title=title,seconds=duration,script=script,extra=extra))


def tiny_network(s,x,y,scale=1,groups=True):
    pts=[(0,.7),(.8,0),(1.5,1.0),(2.4,.3),(2.9,1.4),(3.6,.7)]
    for a,b in [(0,1),(0,2),(1,2),(2,3),(3,4),(3,5),(4,5)]:
        line(s,x+(pts[a][0]+.18)*scale,y+(pts[a][1]+.18)*scale,
             x+(pts[b][0]+.18)*scale,y+(pts[b][1]+.18)*scale,GRAY,2)
    for i,(px,py) in enumerate(pts):circle(s,x+px*scale,y+py*scale,.36*scale,TEAL if i<3 or not groups else BLUE,label=i+1,size=11*scale)


def build():
    original=ROOT/'docs/screenshots/official.jpg'
    shutil.copy2(original,ASSETS/'demo_screen.jpg')
    Image.open(original).crop((16,108,916,617)).save(ASSETS/'network_detail.jpg',quality=95)
    case=json.loads((DATA/'cases/s2_d0.1_help_spaced_t240-summary.json').read_text())['comparison']
    later=json.loads((DATA/'cases/s2_longer_horizon_check.json').read_text())['comparison']
    rumor=json.loads((DATA/'cases/s0_d0.2_gossip_burst_t60-summary.json').read_text())['comparison']
    runs=list(csv.DictReader((DATA/'runs.csv').open(encoding='utf-8-sig')))
    mean=lambda trust,policy,key:sum(float(r[key]) for r in runs if r['trust_condition']==trust and r['policy']==policy)/12
    low_harm=mean('low','harm_burst','delta_ego_degree');high_harm=mean('high','harm_burst','delta_ego_degree')
    low_rumor=mean('low','gossip_burst','delta_subject_liking');high_rumor=mean('high','gossip_burst','delta_subject_liking')

    s=slide('', 'マルチメディア情報特論  /  作品発表')
    text(s,'Social\nRelationship Lab',.72,1.15,6.1,1.6,38,bold=True,font='Avenir Next')
    text(s,'ひとつの行動が、\n関係のかたちを変える。',.75,3.12,6.0,1.45,30,bold=True)
    text(s,'人間関係とコミュニティの変化を\n触って観察する、TouchDesigner作品',.77,5.15,6,1.0,18,MUTED)
    s.shapes.add_picture(str(ASSETS/'network_detail.jpg'),Inches(6.8),Inches(2.0),width=Inches(5.85))
    text(s,'実際の作品画面より',9.1,5.47,3.5,.3,11,MUTED,align=PP_ALIGN.RIGHT)
    note(s,'作品紹介','私が制作したのは、人間関係とコミュニティの変化を触って観察する作品、Social Relationship Labです。一つの行動が、相手だけでなく、周囲との関係にどう波及するのかを表現しました。')

    s=slide('表現したかったこと：自分の行動は、どこまで届くのか。')
    text(s,'誰かを助けたり、攻撃したり、噂を話したりしたとき。\nその人の評価と、周囲とのつながりはどう変わるのか。',.8,1.86,11.8,1.1,25)
    labels=[('自分の行動',GOLD),('相手・周囲の評価',TEAL),('関係・集団の変化',BLUE)]
    for i,(label,c) in enumerate(labels):
        x=.8+i*4.2
        box(s,x,3.4,3.55,2.28,PANEL,radius=True)
        if i==0:
            circle(s,x+.45,3.92,.7,GOLD,'自',20);circle(s,x+2.35,4.3,.54,TEAL,'相',16)
            line(s,x+1.25,4.3,x+2.25,4.55,GOLD,3)
            text(s,'協力・攻撃・噂',x+.4,5.05,2.9,.4,17,MUTED)
        else:tiny_network(s,x+.32,3.76,.73,groups=i==2)
        text(s,label,x,6.02,3.55,.45,22,c,bold=True,align=PP_ALIGN.CENTER)
        if i<2:text(s,'→',x+3.7,4.14,.45,.55,27,MUTED)
    note(s,'作品で表現したかったこと','最初に考えたのは、誰かに親切にしたら、その人だけでなく、周囲からの見られ方も変わるのではないか、ということです。そこで、一人ひとりの好感度と実際の関係を分け、その積み重なりから集団がどう変わるかを見えるようにしました。大きな分裂や合流が必ず起きる演出にはしていません。変化しない場合も含めて、行動の影響を観察する作品にしたかったからです。','図は仕組みを説明する模式図。実験結果ではない。')

    s=slide('デモ：自分を中心に、関係の変化を追う。')
    s.shapes.add_picture(str(ASSETS/'demo_screen.jpg'),Inches(.65),Inches(1.48),width=Inches(8.5))
    for i,(head,body,col) in enumerate([
        ('中央の自分','点が人物、線が関係。\n色は検出した集団。',GOLD),
        ('行動を選ぶ','協力・攻撃・噂を\nボタンから試す。',TEAL),
        ('止めて読む','好感度・関係・\n情報の経路を確認。',BLUE)]):
        y=1.88+i*1.55;circle(s,9.55,y,.4,col,i+1,14)
        text(s,head,10.1,y,2.6,.42,20,col,True)
        text(s,body,9.6,y+.58,3.05,.9,18)
    note(s,'デモ画面','こちらが実際の画面です。中央に自分を固定し、周りの点を他の人物、線を成立した関係として表示しています。色は、つながりから検出した集団です。下のボタンから協力、攻撃、噂を選べます。今は協力を一度実行し、1ステップ進めて停止します。関係線だけでなく、相手からの好感度も確認できます。噂では、情報が誰に届いたかと、評価がどう動いたかを見られます。この画面を使い、行動しなかった場合との差も調べました。','50秒枠。事前に正式TOEを開き、人物1を選択して停止する。協力→1ステップ→詳細確認を20秒程度で見せる。余裕があれば同じ初期値→悪い噂→1ステップを数回。画面切替が不調ならこの実画面だけで説明を続ける。画像はdocs/screenshots/official.jpgの過去の実機確認画面で、後続の実験条件そのものではない。')

    s=slide('同じ初期状態から、二つの世界へ。')
    box(s,.8,2.1,3.2,2.4,PANEL,radius=True);text(s,'同じ人物・同じ関係',1.0,2.4,2.8,.45,20,WHITE,True)
    tiny_network(s,1.0,3.1,.68)
    for y,label,col in [(1.95,'行動しない世界',GRAY),(4.25,'行動する世界',TEAL)]:
        line(s,4.2,3.3,5.1,y+.7,col,2)
        box(s,5.25,y,6.95,1.65,PANEL,radius=True)
        text(s,label,5.55,y+.22,5.9,.5,25,col,True)
        text(s,'通常の交流を続ける' if col==GRAY else '指定した行動を加え、通常の交流を続ける',5.55,y+.92,6.25,.4,17,MUTED)
    text(s,'40人・12シード。関係数、好感度、信頼、集団の違いを比較。',.85,6.28,11.8,.5,21)
    note(s,'比較の方法','結果を読むために、同じ初期状態を二つにコピーしました。一方には行動を加えず、もう一方には指定した行動を加えます。どちらでも通常の交流は続きます。こうして、元から違う人同士を比べるのではなく、同じ人の行動の有無で何が変わったかを調べました。','図は比較設計の模式図。540条件＝介入492＋無操作確認48。数値実験はPythonで実施。詳細は補足11。')

    s=slide('結果①  協力したのに、つながりが少ない？')
    for x,label,values in [(.85,'240ステップ後',[case['final_ego_degree'],case['baseline_ego_degree']]),
                           (7.0,'480ステップ後',[later['final_ego_degree'],later['baseline_ego_degree']])]:
        text(s,label,x,1.85,5.5,.5,24,bold=True)
        baseline_y=5.35
        for j,(value,col,kind) in enumerate(zip(values,[TEAL,GRAY],['協力した世界','行動しない世界'])):
            xx=x+.35+j*2.6;h=value*.23
            box(s,xx,baseline_y-h,1.35,h,col)
            text(s,str(value),xx,baseline_y-h-.63,1.35,.6,37,col,True,align=PP_ALIGN.CENTER)
            text(s,kind,xx-.3,5.6,2.2,.4,17,col,align=PP_ALIGN.CENTER)
    text(s,'→',6.2,3.55,.6,.6,32,GOLD)
    box(s,.8,6.22,11.8,.48,PANEL)
    text(s,'240時点でも好感度は協力側が高い。元の友人を失わず、新しい関係の成立に差。',1.0,6.3,11.4,.35,17)
    note(s,'面白かった結果：時間による逆転','一つ目は、協力した方が、つながりが少なくなった例です。全ての知人に、間隔を空けて5回協力しました。240ステップ後、協力した世界は関係が5本、何もしない世界は6本でした。それでも、周りからの好感度は協力した方が高いままです。元の友人を失ったのではなく、何もしない世界だけが新しい相手と関係を作っていました。履歴では、協力に時間を使ったとき、通常の交流が時間不足になる場面も確認できました。ただし、さらに480ステップまで追うと、今度は協力側が10本、無操作側が9本と逆転しました。協力が悪い、とは言えません。どの時点を見るかによっても、評価が変わることが面白いと思いました。','seed2、密度0.10、help_spaced。240時点：受信好感度差+0.09848489。元の5関係は全て維持。480は発見後の追加確認で事前固定540条件外。240の不利は協力2方針×12シードの24条件中1例で、確認群では未再現。単一の招待だけを最終差の原因とは断定しない。出典：cases/s2_d0.1_help_spaced_t240-summary.json、s2_longer_horizon_check.json。')

    s=slide('結果②  噂が全員に届いても、関係線は変わらない。')
    nums=[('39','人','噂を知った人数',GOLD),
          (f'{rumor["delta_subject_liking"]:.3f}','','対象の平均好感度の差',CORAL),
          (str(rumor['compare_tie_difference']),'本','対照と異なる関係線',BLUE)]
    for i,(value,unit,label,col) in enumerate(nums):
        x=.8+i*4.2;box(s,x,2.03,3.56,3.25,PANEL,radius=True)
        text(s,value,x+.15,2.58,3.25,1.0,56,col,True,align=PP_ALIGN.CENTER)
        text(s,unit,x+.15,3.65,3.25,.4,19,col,align=PP_ALIGN.CENTER)
        text(s,label,x+.12,4.45,3.32,.55,18,WHITE,align=PP_ALIGN.CENTER)
    text(s,'伝わること、評価が動くこと、関係を切ることは別。',.85,5.95,11.7,.55,26,bold=True)
    text(s,'40人の社会・悪い噂5回の一例。密な社会では12条件中11条件で、関係線の違いは0。',.85,6.58,11.8,.3,13,MUTED)
    note(s,'面白かった結果：噂の到達と関係','二つ目は噂です。40人のうち発信者以外の39人、つまり全員が噂を知った例がありました。対象の人物への平均好感度は、無操作の世界より約0.066下がっています。ところが、関係線の違いは0本でした。情報が届いても、評価が変わっても、実際に関係を切るとは限りません。これは一例だけでなく、密な社会の12条件中11条件で、関係線に違いが出ませんでした。線だけを眺めると見落としてしまう変化を、情報と好感度の表示でも見られるようにした意味がありました。','seed0、密度0.20、gossip_burst、介入後60時刻。39人は5イベントの受信者の和集合、発信者を除く。0本は無操作世界との異なる辺数であり、初期から一切の形成・切断がないという意味ではない。出典：cases/s0_d0.2_gossip_burst_t60-summary.json、runs.csv。')

    s=slide('結果③  信頼は、関係を守り、噂の影響も強める。')
    charts=[(.8,'攻撃5連続による関係数の差',[-low_harm,-high_harm],4,CORAL,2),
            (7.05,'噂5連続による対象好感度の差',[-low_rumor,-high_rumor],.19,GOLD,3)]
    for x,title,values,limit,col,decimals in charts:
        text(s,title,x,1.9,5.5,.55,20,bold=True)
        for j,(value,label) in enumerate(zip(values,['低信頼','高信頼'])):
            y=2.95+j*1.13;text(s,label,x,y,1.25,.4,18,MUTED)
            box(s,x+1.3,y+.02,value/limit*3.0,.3,col)
            text(s,f'−{value:.{decimals}f}',x+1.3,y+.44,3.7,.5,25,col,True)
    box(s,.8,5.68,11.8,.78,PANEL)
    text(s,'同じ「信頼」が、攻撃の緩衝と、情報の信用度の両方に働く。',1.0,5.88,11.4,.42,22)
    text(s,'既存関係の信頼を低／高に設定。各12シードの平均・行動なしとの差。',.85,6.65,11.8,.3,13,MUTED)
    note(s,'面白かった結果：信頼の二面性','三つ目は信頼の二面性です。既存関係の信頼を低い状態と高い状態に設定して比較すると、信頼が高い集団では、攻撃を繰り返したときの関係損失が小さくなりました。一方、悪い噂による対象の評判低下は、高信頼の集団の方が大きくなりました。信頼があるから関係は守られるけれど、情報も信用されやすい、ということです。この方向は、信頼を攻撃の緩衝と噂の信用度に使った式にも依存しています。人間の新しい法則を発見したのではなく、自分たちの仮定がどんな結果を生むかが見えた例です。','密度0.10、全既存関係の介入時信頼を0.15／0.85に設定。低信頼の攻撃平均差約−3.17、高信頼約−1.92。噂対象の受信好感度差は約−0.0410／−0.1723。図は差の絶対値を棒の長さで表示し、符号を数値に残す。1人の信頼だけを変更した比較ではない。出典：runs.csv。')

    s=slide('この作品で、見えるようにしたこと。')
    text(s,'好かれること。\nつながること。\n集団が変わること。',.85,2.0,6.4,2.65,36,bold=True)
    for y,txt,col in [(2.2,'結果は、見る時点で変わる。',TEAL),
                      (3.45,'情報と関係は、別々に動く。',GOLD),
                      (4.7,'信頼の働きは、一方向ではない。',BLUE)]:
        box(s,7.1,y+.04,.06,.45,col);text(s,txt,7.4,y,5.15,.7,21,col,True)
    text(s,'同じ初期状態から、行動の影響を試せる作品にした。',.85,6.05,11.7,.6,27,bold=True)
    link(s,'作品・実験記録： github.com/maton369/social-relationship-lab','https://github.com/maton369/social-relationship-lab',.85,6.72,10,12)
    note(s,'まとめ','この作品では、好かれること、実際につながること、集団が変わることを、それぞれ別の変化として見えるようにしました。同じ初期状態から行動を変えて、何が変わり、何が変わらなかったのかを試せることが、作品の中心です。発表は以上です。','ここで本編終了。累計5分。以降は質問があった場合だけ表示する。現実社会の予測精度は検証していない。')

    s=slide('仕様：好感度・関係・信頼・集団を分ける。')
    rows=[('好感度 X','方向付き、−1〜1。好きの向きは非対称。','人物iから人物jへの評価。自己評価は平均から除外。'),
          ('関係 A','相互関係、0／1。成立には双方の好意。','切断は一方の評価が切断閾値以下になると発生。'),
          ('信頼 T','好感度と別の方向付き状態、0〜1。','直接経験で学習。攻撃の緩衝・伝聞の信用度に使用。'),
          ('コミュニティ','A上でCPMをLeidenにより最適化。','3人以上を主要集団、2人は二者関係。主観的所属ではない。')]
    for i,(a,b,c) in enumerate(rows):
        y=1.85+i*1.18;box(s,.8,y,11.75,1.04,PANEL)
        text(s,a,1.0,y+.16,2.4,.5,21,TEAL,True)
        text(s,b,3.5,y+.12,8.7,.44,20)
        text(s,c,3.5,y+.6,8.7,.35,14,MUTED)
    text(s,'人物の座標と魚眼変換は描画専用。関係生成には使わない。',.85,6.76,11.4,.3,13,MUTED)
    note(s,'補足：状態と集団','人物数初期値40。人物属性は成立閾値h、切断閾値l、感受性s、拡散傾向b。l<h。内部ハブ、橋渡し、孤立などは独立のタグと連続値で分析する。CPMはQ=ΣC[mC−γ|C|(|C|−1)/2]、γ=0.25。実装はmodel.py、social_dynamics.py、community.py。','コミュニティの理論出典は補足13。集団検出は大域最適や本当の所属を保証しない。')

    s=slide('仕様：実際の更新規則と独自の仮定。')
    blocks=[('直接の協力・攻撃','協力：ΔX[v,u] = +0.50 × 強度\n攻撃：ΔX[v,u] = −0.50 × 強度 × (1 − 0.85T[v,u])'),
            ('噂と情報伝播','噂：ΔX[i,v] = −0.30 × 強度 × s[i] × 信用度\n伝達確率：0.70 × A[i,j] × b[i]（新規受信者が一度だけ試行）'),
            ('関係と交流時間','成立：双方が成立閾値以上 ＋ 接触機会\n切断：どちらかが切断閾値以下 ／ 行動の時間上限1を人数配分')]
    for i,(head,body) in enumerate(blocks):
        y=1.9+i*1.4;text(s,head,.85,y,2.6,.5,20,TEAL,True)
        text(s,body,3.6,y,8.7,1.02,19)
    text(s,'これらの係数・式は試作の独自仮定。論文の実測値や収束保証ではない。',.85,6.5,11.8,.48,18,GOLD)
    note(s,'補足：更新式','自律交流ありのadaptiveモード。攻撃の式は履歴・信頼が有効な場合。同時刻の評価変化は旧状態から計算し合算してクリップ。噂の信用度はT[i,source]に送り手と対象の対立割引を掛ける。初期Xは非関係者N(0,.35²)、既存関係U(.65,.90)。閾値h=.55±.07、l=.25±.05。s=.65±.15、b=.55±.15。q0=.03、共通友人による機会増分.10。自律交流は旧状態から全提案を決め、時間予算の範囲で受諾・拒絶を処理。好感度と信頼の更新、情報・関係・集団検出を分離。','詳細仕様：docs/social-dynamics.md。噂の真偽・嘘の訂正・同じ主張のclaim_id・送り手への制裁は未実装。')

    s=slide('検証：540条件と、結論を広げすぎないための限界。')
    specs=[('396条件','12シード × 3密度 × 11方針\n10ステップ準備 ＋ 60ステップ観測'),
           ('96条件','12シード × 低／高信頼 × 4方針\n密度0.10、既存関係の信頼のみ統制'),
           ('48条件','12シード × 4方針の長期比較\n密度0.10、240ステップ観測')]
    for i,(head,body) in enumerate(specs):
        x=.8+i*4.2;box(s,x,1.9,3.55,2.0,PANEL,radius=True)
        text(s,head,x+.22,2.12,3.1,.65,32,TEAL,True)
        text(s,body,x+.22,2.97,3.15,.76,14)
    text(s,'検査したこと',.85,4.2,3,.4,21,TEAL,True)
    text(s,'初期状態の完全一致 ／ 共通の外生乱数 ／ 対照世界の不変性 ／ 完全再実行\n既存41件＋実験手順3件の自動テスト、計44件通過。',.85,4.78,11.6,1.0,18)
    text(s,'540条件は独立な540標本ではない。全終了時点は未収束。\n逆転の480ステップ確認は発見後の追加1件。現実社会の予測精度は未検証。',.85,6.0,11.6,.85,17,GOLD)
    note(s,'補足：条件と限界','自然条件のシードは0〜5と100〜105。初期密度.05/.10/.20。540条件には無操作確認48条件を含む。探索群・確認群で同じ方針を実施。人物単位ではなくシード単位で集計・再標本化。同じ数値モデルをPythonで実行しており、540条件をTouchDesignerのボタンから操作したわけではない。代表2例は全状態JSONを保存して再実行のダイジェスト一致を確認。個人属性や社会的概念は合成で実測から校正していない。','実験手順：docs/experiments/conditions-and-policies/protocol.md。データ：runs.csv、long-horizon/runs.csv、integrity-checks.json。')

    s=slide('参考文献：社会関係・信頼・噂の着想。')
    refs=[('Sutcliffe, A., Wang, D. & Dunbar, R. (2012)',
           'Social Relationships and the Emergence of Social Networks. JASSS, 15(4), 3.',
           'https://doi.org/10.18564/jasss.2059',
           '参照：交流履歴・限られた時間・信頼。信頼更新式や係数は独自拡張。'),
          ('Rand, D. G., Arbesman, S. & Christakis, N. A. (2011)',
           'Dynamic social networks promote cooperation in experiments with humans. PNAS, 108(48), 19193–19198.',
           'https://doi.org/10.1073/pnas.1108243108',
           '参照：協力に応じた関係更新。原研究は本作の時間制約や攻撃の式を検証していない。'),
          ('Dores Cruz, T. D. et al. (2021)',
           'Gossip and reputation in everyday life. Philosophical Transactions of the Royal Society B, 376, 20200301.',
           'https://doi.org/10.1098/rstb.2020.0301',
           '参照：噂による評判更新。信用度をTで表す式・反復加算は独自仮定。')]
    for i,(authors,title,url,relation) in enumerate(refs):
        y=1.86+i*1.58;text(s,authors,.85,y,11.5,.4,19,bold=True)
        text(s,title,.85,y+.43,11.5,.58,14,MUTED,font='Avenir Next')
        link(s,url,url,.85,y+1.0,11.5,13)
        text(s,relation,.85,y+1.34,11.5,.35,13,TEAL)
    note(s,'補足：社会関係の参考文献','いずれも論文の仕組みをそのまま移植したものではなく、概念に着想を得た独自拡張。Sutcliffeは全文HTML、RandとDores Cruzは公開PDF本文を確認。論文の係数や収束保証を今回のモデルに転用しない。','本作との対応：docs/references.md。今回の解釈：docs/conditions-and-actions.md。引用は要約で、論文図版は転載していない。')

    s=slide('参考文献・配布：集団検出と、再現できる実験記録。')
    refs=[('Traag, V. A., Van Dooren, P. & Nesterov, Y. (2011)',
           'Narrow scope for resolution-limit-free community detection. Physical Review E, 84, 016114.',
           'https://doi.org/10.1103/PhysRevE.84.016114','CPMの目的関数。γ=0.25は本作の仮設定。'),
          ('Traag, V. A., Waltman, L. & van Eck, N. J. (2019)',
           'From Louvain to Leiden: guaranteeing well-connected communities. Scientific Reports, 9, 5233.',
           'https://doi.org/10.1038/s41598-019-41695-z','Leidenによる最適化。大域最適・実際の所属・本作の社会力学の収束は保証しない。')]
    for i,(authors,title,url,relation) in enumerate(refs):
        y=1.85+i*1.65;text(s,authors,.85,y,11.5,.4,19,bold=True)
        text(s,title,.85,y+.44,11.5,.58,14,MUTED,font='Avenir Next')
        link(s,url,url,.85,y+1.03,11.5,13);text(s,relation,.85,y+1.37,11.5,.4,13,TEAL)
    box(s,.8,5.56,11.8,1.1,PANEL)
    link(s,'作品・コード： https://github.com/maton369/social-relationship-lab','https://github.com/maton369/social-relationship-lab',1.0,5.75,11.3,15)
    link(s,'結果・全試行CSV： docs/conditions-and-actions.md','https://github.com/maton369/social-relationship-lab/blob/main/docs/conditions-and-actions.md',1.0,6.18,11.3,14)
    note(s,'補足：集団検出・配布','CPMとLeidenの書誌情報はarXivの著者原稿ページでも確認。CPMはigraph/leidenalgで計算する。実際の関係グラフだけから推定し、好感度・心理的所属と混同しない。配布するファイルはSocial_Relationship_Lab.toe一つで、対応ライブラリを内蔵。Mac Apple Siliconで実機確認済み。Windows x64向けも同梱するがWindows描画実機確認は未実施。','画像出典：本リポジトリのTouchDesigner実画面。実験値出典：本リポジトリ保存の合成データ。画面と図表に外部画像や架空の実験結果は使用していない。')

    prs.core_properties.title='Social Relationship Lab — 5分作品発表'
    prs.core_properties.subject='人間関係・コミュニティの共進化を可視化するTouchDesigner作品'
    prs.core_properties.author='Social Relationship Lab project'
    prs.core_properties.keywords='TouchDesigner, social networks, lecture, 5 minutes'
    prs.save(HERE/'Social_Relationship_Lab.pptx')
    (HERE/'slide-notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf-8')
    md=['# 5分発表：読み上げ原稿と操作メモ','',
        '本編は1〜8枚、合計300秒。9〜13枚は質疑用の補足。時間にはデモ操作を含む。','',
        '| スライド | 内容 | 持ち時間 | 累計 |','| --- | --- | ---: | ---: |']
    elapsed=0
    for n in notes[:8]:
        elapsed+=n['seconds'];md.append(f'| {n["number"]} | {n["title"]} | {n["seconds"]}秒 | {elapsed//60}:{elapsed%60:02d} |')
    for n in notes:
        md+=['',f'## {n["number"]}. {n["title"]}','',n['script']]
        if n['extra']:md+=['','操作・出典・留意点：'+n['extra']]
    (HERE/'speaker-notes.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    (HERE/'provenance.json').write_text(json.dumps(dict(
        screenshot='docs/screenshots/official.jpg (Mac実機画面。結果例の実験条件とは別)',
        main_slides=8,appendix_slides=5,total_seconds=sum(timings),
        cooperation_case='docs/experiments/conditions-and-policies/cases/s2_d0.1_help_spaced_t240-summary.json',
        later_case='docs/experiments/conditions-and-policies/cases/s2_longer_horizon_check.json',
        gossip_case='docs/experiments/conditions-and-policies/cases/s0_d0.2_gossip_burst_t60-summary.json',
        trust_comparison='docs/experiments/conditions-and-policies/runs.csv',
        reference_links=['https://www.jasss.org/15/4/3.html','https://doi.org/10.1073/pnas.1108243108',
          'https://doi.org/10.1098/rstb.2020.0301','https://arxiv.org/abs/1104.3083','https://arxiv.org/abs/1810.08473']),
        ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Saved {len(prs.slides)} slides, {sum(timings)} seconds, editable PPTX + notes.')


if __name__=='__main__':build()
