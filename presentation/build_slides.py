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
TEMPLATE=ASSETS/'tcu_template.pptx'
if not TEMPLATE.exists():
    shutil.copy2(ROOT.parents[1]/'【FMT】背景_東京都市大学.pptx',TEMPLATE)
BG='#FFFFFF'; PANEL='#EEF5F8'; WHITE='#182D41'; MUTED='#536779'
TEAL='#087C73'; GOLD='#A05E08'; CORAL='#B5424A'; GRAY='#7C8B99'; BLUE='#005D93'
FONT='Hiragino Sans'
prs=Presentation(TEMPLATE)
for sid in list(prs.slides._sldIdLst):
    prs.part.drop_rel(sid.rId);prs.slides._sldIdLst.remove(sid)
notes=[];target_seconds=240


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
    s=prs.slides.add_slide(prs.slide_layouts[0 if not len(prs.slides) else 1])
    if len(prs.slides)==1:
        # The cover uses the actual title/subtitle placeholders, including their
        # inherited positions, typography, alignment and vertical anchoring.
        return s
    for v in list(s.shapes):
        if v.is_placeholder and v.placeholder_format.idx!=0:v._element.getparent().remove(v._element)
    s.background.fill.solid();s.background.fill.fore_color.rgb=rgb(BG)
    header=s.shapes.title;header.text=title or tag
    return s


def note(s,title,script,extra=''):
    n=len(prs.slides)
    # The notes pane is a spoken script, with no timing or technical reminders.
    s.notes_slide.notes_text_frame.text=script
    notes.append(dict(number=n,title=title,script=script,reference_context=extra))


def tiny_network(s,x,y,scale=1,groups=True):
    pts=[(0,.7),(.8,0),(1.5,1.0),(2.4,.3),(2.9,1.4),(3.6,.7)]
    for a,b in [(0,1),(0,2),(1,2),(2,3),(3,4),(3,5),(4,5)]:
        line(s,x+(pts[a][0]+.18)*scale,y+(pts[a][1]+.18)*scale,
             x+(pts[b][0]+.18)*scale,y+(pts[b][1]+.18)*scale,GRAY,2)
    for i,(px,py) in enumerate(pts):circle(s,x+px*scale,y+py*scale,.36*scale,TEAL if i<3 or not groups else BLUE,label=i+1,size=11*scale)


def build():
    original=ROOT/'docs/screenshots/interface_overview.jpg'
    shutil.copy2(original,ASSETS/'demo_screen.jpg')
    shutil.copy2(ROOT/'docs/screenshots/interface_comparison.jpg',ASSETS/'demo_comparison.jpg')
    Image.open(original).crop((16,108,916,617)).save(ASSETS/'network_detail.jpg',quality=95)
    case=json.loads((DATA/'cases/s2_d0.1_help_spaced_t240-summary.json').read_text())['comparison']
    later=json.loads((DATA/'cases/s2_longer_horizon_check.json').read_text())['comparison']
    rumor=json.loads((DATA/'cases/s0_d0.2_gossip_burst_t60-summary.json').read_text())['comparison']
    runs=list(csv.DictReader((DATA/'runs.csv').open(encoding='utf-8-sig')))
    mean=lambda trust,policy,key:sum(float(r[key]) for r in runs if r['trust_condition']==trust and r['policy']==policy)/12
    low_harm=mean('low','harm_burst','delta_ego_degree');high_harm=mean('high','harm_burst','delta_ego_degree')
    low_rumor=mean('low','gossip_burst','delta_subject_liking');high_rumor=mean('high','gossip_burst','delta_subject_liking')

    s=slide('', 'マルチメディア情報特論  /  作品発表')
    s.shapes.title.text='人間関係シミュレーター'
    s.placeholders[1].text=('ひとつの行動が、関係のかたちを変える。\n'
                            '人間関係・コミュニティを観察するTouchDesigner作品\n'
                            'マルチメディア情報特論')
    note(s,'作品紹介','制作したのは「人間関係シミュレーター」です。一つの行動が、相手だけでなく周囲との関係をどう変えるかを、触って観察する作品です。')

    s=slide('行動は、どこまで届くのか')
    text(s,'誰かを助け、攻撃し、悪い評判を広めたとき。\nその人の評価と、周囲とのつながりはどう変わるのか。',.8,1.86,11.8,1.1,25)
    labels=[('自分の行動',GOLD),('相手・周囲の評価',TEAL),('関係・集団の変化',BLUE)]
    for i,(label,c) in enumerate(labels):
        x=.8+i*4.2
        box(s,x,3.4,3.55,2.28,PANEL,radius=True)
        if i==0:
            circle(s,x+.45,3.92,.7,GOLD,'自',20);circle(s,x+2.35,4.3,.54,TEAL,'相',16)
            line(s,x+1.25,4.3,x+2.25,4.55,GOLD,3)
            text(s,'協力・攻撃・悪い噂',x+.4,5.05,2.9,.4,17,MUTED)
        else:tiny_network(s,x+.32,3.76,.73,groups=i==2)
        text(s,label,x,6.02,3.55,.45,22,c,bold=True,align=PP_ALIGN.CENTER)
        if i<2:text(s,'→',x+3.7,4.14,.45,.55,27,MUTED)
    note(s,'作品で表現したかったこと','誰かを助けたり、攻撃したり、悪い噂を広めたりすると、周囲の見方も変わります。そこで、好感度、信頼、実際の関係を分けて持たせ、その積み重なりから集団がどう変わるかを表現しました。大きな分裂を演出するのではなく、変わらない結果もそのまま見られるようにしています。','図は仕組みを説明する模式図。実験結果ではない。')

    s=slide('自分を中心に関係を観察')
    s.shapes.add_picture(str(ASSETS/'demo_screen.jpg'),Inches(.65),Inches(1.48),width=Inches(8.5))
    for i,(head,body,col) in enumerate([
        ('中央の自分','点が人物、線が関係。\n色は検出した集団。',GOLD),
        ('行動を選ぶ','協力する・攻撃する・\n悪い噂を広める。',TEAL),
        ('止めて読む','つながり・好かれ度・\n信頼度を大きく確認。',BLUE)]):
        y=1.88+i*1.55;circle(s,9.55,y,.4,col,i+1,14)
        text(s,head,10.1,y,2.6,.42,20,col,True)
        text(s,body,9.6,y+.58,3.05,.9,18)
    note(s,'デモ画面','こちらが現在の画面です。点が人物、線が関係、色が集団です。中央に自分を固定し、右にはつながり、好かれ度、信頼度を表示しています。「協力する」を押し、1ステップ進めて変化を確認します。人物1の協力と攻撃は知人全員が対象です。悪い噂は、選んだ人の悪い評判を知人へ伝える操作で、真偽は扱いません。','事前に正式TOEを開き、人物1を中心に停止する。「協力する」→「1ステップ」→右の数値確認を手短に見せる。余裕があれば「やり直す」→右クリックで噂の対象を選ぶ→「悪い噂を広める」→「1ステップ」を数回。噂の対象本人には直接伝えず、伝播の途中で本人が知る場合はある。真偽は扱わない。画面切替が不調なら実画面の静止画で説明する。画像はdocs/screenshots/interface_overview.jpg（2026年11月12日の実機確認画面）。後続の結果例とは別の条件。')

    s=slide('同じ初期状態から比較する')
    s.shapes.add_picture(str(ASSETS/'demo_comparison.jpg'),Inches(.65),Inches(1.48),width=Inches(8.5))
    for y,head,body,col in [(1.98,'左と右を比べる','左：何もしない場合\n右：行動した場合',BLUE),
                           (3.67,'橙線は好感度の差','横：時間、縦：差の大きさ\n良し悪しの点数ではない。',GOLD),
                           (5.4,'同じ初期状態','同じ人物・同じ関係から\n行動の有無だけを変える。',TEAL)]:
        text(s,head,9.6,y,3.05,.5,20,col,True)
        text(s,body,9.6,y+.6,3.05,.95,16)
    note(s,'比較の方法','同じ初期状態から、左は何もしない世界、右は行動する世界を動かします。どちらでも通常の交流は続きます。オレンジ線は両者の好感度の差で、大きいほど良いという点数ではありません。','「関係図」ボタンから表示を切り替えると、関係図→好感度→情報の流れ→行動比較の順で進む。オレンジ線は通常画面では非表示、行動比較で一つだけ表示する。縦軸は全ての他者評価ペアの平均絶対差、範囲は自動調整して画面下に表示。横軸はシミュレーション時刻。画像はdocs/screenshots/interface_comparison.jpg（2026年11月12日の実機確認画面、介入後8ステップ）。後続の研究例とは別条件。540条件＝介入492＋無操作確認48。数値実験の詳細は補足11。')

    s=slide('協力したのに、つながりが少ない？')
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
    note(s,'面白かった結果：時間による逆転','面白かったのは、協力しても関係が増えるとは限らなかったことです。知人全員に間隔を空けて5回協力した例では、240ステップ後の関係数は協力側が5本、何もしない側が6本でした。好感度は協力側の方が高く、元の友人も失っていません。新しい関係ができる時期に差があったのです。さらに480ステップまで追うと、協力側が10本、無操作側が9本と逆転しました。協力の良し悪しを一時点だけで判断できないと分かりました。','seed2、密度0.10、help_spaced。240時点：受信好感度差+0.09848489。元の5関係は全て維持。480は発見後の追加確認で事前固定540条件外。240の不利は協力2方針×12シードの24条件中1例で、確認群では未再現。単一の招待だけを最終差の原因とは断定しない。出典：cases/s2_d0.1_help_spaced_t240-summary.json、s2_longer_horizon_check.json。')

    s=slide('噂が届いても、関係は変わらない')
    text(s,'悪い噂＝選んだ人物の悪い評判を、知人に伝える操作。',.85,1.55,11.8,.4,18,MUTED)
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
    note(s,'面白かった結果：噂の到達と関係','次は悪い噂です。発信者以外の39人全員に届き、対象への平均好感度は無操作側より約0.066下がりました。でも、関係線の違いは0本でした。密な社会では、12条件中11条件で同じように関係線の違いが出ませんでした。情報が届くこと、評価が動くこと、関係を切ることは、それぞれ別なのです。','seed0、密度0.20、gossip_burst、介入後60時刻。39人は5イベントの受信者の和集合、発信者を除く。0本は無操作世界との異なる辺数であり、初期から一切の形成・切断がないという意味ではない。出典：cases/s0_d0.2_gossip_burst_t60-summary.json、runs.csv。')

    s=slide('信頼が守り、噂を強める')
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
    note(s,'面白かった結果：信頼の二面性','信頼にも二つの働きがありました。信頼を高く設定した集団では、攻撃を繰り返したときの関係損失が小さくなりました。一方、悪い噂による評判低下は大きくなりました。関係が守られると同時に、情報も信用されやすくなるためです。この結果は設定した式にも依存し、現実の人間で確認した法則ではありません。','密度0.10、全既存関係の介入時信頼を0.15／0.85に設定。低信頼の攻撃平均差約−3.17、高信頼約−1.92。噂対象の受信好感度差は約−0.0410／−0.1723。図は差の絶対値を棒の長さで表示し、符号を数値に残す。1人の信頼だけを変更した比較ではない。出典：runs.csv。')

    s=slide('作品で見えるようにしたこと')
    text(s,'好かれること。\nつながること。\n集団が変わること。',.85,2.0,6.4,2.65,36,bold=True)
    for y,txt,col in [(2.2,'結果は、見る時点で変わる。',TEAL),
                      (3.45,'情報と関係は、別々に動く。',GOLD),
                      (4.7,'信頼の働きは、一方向ではない。',BLUE)]:
        box(s,7.1,y+.04,.06,.45,col);text(s,txt,7.4,y,5.15,.7,21,col,True)
    text(s,'同じ初期状態から、行動の影響を試せる作品にした。',.85,6.05,11.7,.6,27,bold=True)
    link(s,'作品・実験記録： github.com/maton369/social-relationship-lab','https://github.com/maton369/social-relationship-lab',.85,6.72,10,12)
    note(s,'まとめ','この作品では、好かれること、つながること、集団が変わることを、別々の変化として見えるようにしました。同じ初期状態から行動を変え、その影響を試せることが作品の中心です。以上です。','ここで本編終了。以降は質問があった場合だけ表示する。現実社会の予測精度は検証していない。')

    s=slide('仕様：好感度・関係・信頼')
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
    note(s,'補足：状態と集団','','通常画面の「好かれ度」は自己を除く全人物からの好感度Xの平均、「信頼度」は同じ人物集合からの信頼Tの平均。非関係者も含む。細かな属性・閾値・分析値は「詳細」にある。コミュニティの理論出典は補足13。集団検出は大域最適や本当の所属を保証しない。')

    s=slide('仕様：更新規則と独自の仮定')
    blocks=[('直接の協力・攻撃','協力：ΔX[v,u] = +0.50 × 強度\n攻撃：ΔX[v,u] = −0.50 × 強度 × (1 − 0.85T[v,u])'),
            ('噂と情報伝播','噂：ΔX[i,v] = −0.30 × 強度 × s[i] × 信用度\n伝達確率：0.70 × A[i,j] × b[i]（新規受信者が一度だけ試行）'),
            ('関係と交流時間','成立：双方が成立閾値以上 ＋ 接触機会\n切断：どちらかが切断閾値以下 ／ 行動の時間上限1を人数配分')]
    for i,(head,body) in enumerate(blocks):
        y=1.9+i*1.4;text(s,head,.85,y,2.6,.5,20,TEAL,True)
        text(s,body,3.6,y,8.7,1.02,19)
    text(s,'これらの係数・式は試作の独自仮定。論文の実測値や収束保証ではない。',.85,6.5,11.8,.48,18,GOLD)
    note(s,'補足：更新式','','詳細仕様：docs/social-dynamics.md。噂の真偽・嘘の訂正・同じ主張のclaim_id・送り手への制裁は未実装。')

    s=slide('検証の範囲と限界')
    specs=[('396条件','12シード × 3密度 × 11方針\n10ステップ準備 ＋ 60ステップ観測'),
           ('96条件','12シード × 低／高信頼 × 4方針\n密度0.10、既存関係の信頼のみ統制'),
           ('48条件','12シード × 4方針の長期比較\n密度0.10、240ステップ観測')]
    for i,(head,body) in enumerate(specs):
        x=.8+i*4.2;box(s,x,1.9,3.55,2.0,PANEL,radius=True)
        text(s,head,x+.22,2.12,3.1,.65,32,TEAL,True)
        text(s,body,x+.22,2.97,3.15,.76,14)
    text(s,'検査したこと',.85,4.2,3,.4,21,TEAL,True)
    text(s,'初期状態の完全一致 ／ 共通の外生乱数 ／ 対照世界の不変性 ／ 完全再実行\n数値実験時44件、現行UIの確認を含めて自動テスト47件通過。',.85,4.78,11.6,1.0,18)
    text(s,'540条件は独立な540標本ではない。全終了時点は未収束。\n逆転の480ステップ確認は発見後の追加1件。現実社会の予測精度は未検証。',.85,6.0,11.6,.85,17,GOLD)
    note(s,'補足：条件と限界','比較したのは40人の社会で、12個のシードを使った540条件です。無操作の確認48条件も含みます。初期状態と外から与える乱数を対応させ、結果の完全再現も確認しました。ただし540個の独立した標本ではなく、観測終了時点で数学的な収束も確認していません。現実の人間関係の予測精度は未検証です。','数値実験の時点は44テスト。2026年11月12日のUI更新で、噂の人物区別と要約、通常画面の折れ線非表示の3件を追加し47件通過。Mac実機で協力・攻撃・噂・1ステップ・停止再開・詳細10表示を確認。更新は表示だけで数値モデルの式は同じ。実機記録：docs/interface-checks.json。実験手順：docs/experiments/conditions-and-policies/protocol.md。データ：runs.csv、long-horizon/runs.csv、integrity-checks.json。')

    s=slide('参考文献：社会関係と噂')
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
    note(s,'補足：社会関係の参考文献','交流履歴や信頼、時間配分はSutcliffeら、行動に応じた関係更新はRandら、噂による評判更新はDores Cruzらの研究を参考にしています。ただし、今回の式や係数をこれらの研究が実証したわけではなく、考え方を参考にした独自のモデルです。','本作との対応：docs/references.md。今回の解釈：docs/conditions-and-actions.md。引用は要約で、論文図版は転載していない。')

    s=slide('参考文献：集団検出と配布')
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
    note(s,'補足：集団検出・配布','集団の検出には、関係の内部密度を評価するCPMと、その最適化を行うLeidenを使いました。これは実際の関係から推定した構造的な集団で、本人の所属意識を表すものではありません。作品、コード、実験記録は、こちらのGitHubで公開しています。','画像出典：本リポジトリのTouchDesigner実画面。実験値出典：本リポジトリ保存の合成データ。画面と図表に外部画像や架空の実験結果は使用していない。')

    # Keep the supplied university master, logo and campus footer intact. Reserve
    # their header/footer space by mapping only our content into the body region.
    for page in list(prs.slides)[1:]:
        for shape in page.shapes:
            if shape.name.startswith('TCU_CHROME_') or shape.is_placeholder:continue
            shape.top=int(Inches(.07)+shape.top*.88)
            shape.height=int(shape.height*.88)
            if shape.shape_type==13:
                width=shape.width
                shape.width=int(width*.88);shape.left+=int(width*.06)
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    if p.font.size:p.font.size=Pt(p.font.size.pt*.92)
                    if p.space_after:p.space_after=Pt(p.space_after.pt*.88)
    prs.core_properties.title='人間関係シミュレーター — 4分作品発表'
    prs.core_properties.subject='人間関係・コミュニティの共進化を可視化するTouchDesigner作品'
    prs.core_properties.author='人間関係シミュレーター 制作チーム'
    prs.core_properties.keywords='TouchDesigner, social networks, lecture, 4 minutes'
    prs.save(HERE/'Social_Relationship_Lab.pptx')
    (HERE/'slide-notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf-8')
    md=['# 発表台本','',
        '本編は1〜8枚。仕様を除く補足の台本は質疑用。PowerPointのノートにも同じ台本を記載。']
    for n in notes:
        if not n['script']:continue
        md+=['',f'## {n["number"]}. {n["title"]}','',n['script']]
    (HERE/'speaker-notes.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    (HERE/'provenance.json').write_text(json.dumps(dict(
        template='【FMT】背景_東京都市大学.pptx (provided in workspace; master/layouts/logo/footer preserved)',
        cover_layout='Original タイトル スライド; title/subtitle placeholders and inherited formatting preserved',
        screenshot='docs/screenshots/interface_overview.jpg (2026-11-12 Mac実機画面。結果例の実験条件とは別)',
        comparison_screenshot='docs/screenshots/interface_comparison.jpg (2026-11-12 Mac実機画面。結果例の実験条件とは別)',
        interface_release_toe_sha256=json.loads((ROOT/'docs/interface-checks.json').read_text(encoding='utf-8'))['release_toe_sha256'],
        title_layout='Every content slide uses the original タイトルとコンテンツ title placeholder, with inherited formatting',
        main_slides=8,appendix_slides=5,target_seconds=target_seconds,
        script_slides=[n['number'] for n in notes if n['script']],specification_slides=[9,10],
        cooperation_case='docs/experiments/conditions-and-policies/cases/s2_d0.1_help_spaced_t240-summary.json',
        later_case='docs/experiments/conditions-and-policies/cases/s2_longer_horizon_check.json',
        gossip_case='docs/experiments/conditions-and-policies/cases/s0_d0.2_gossip_burst_t60-summary.json',
        trust_comparison='docs/experiments/conditions-and-policies/runs.csv',
        reference_links=['https://www.jasss.org/15/4/3.html','https://doi.org/10.1073/pnas.1108243108',
          'https://doi.org/10.1098/rstb.2020.0301','https://arxiv.org/abs/1104.3083','https://arxiv.org/abs/1810.08473']),
        ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Saved {len(prs.slides)} slides; four-minute presentation, spoken notes without timing labels.')


if __name__=='__main__':build()
