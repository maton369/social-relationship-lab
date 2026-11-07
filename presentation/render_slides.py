"""Render the deck's simple editable geometry to SVG/PDF without an Office importer."""
from pathlib import Path
from html import escape
import base64
import json
import os
import subprocess
from PIL import Image,ImageFont,ImageDraw
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE,MSO_SHAPE
from pptx.enum.text import PP_ALIGN,MSO_ANCHOR

HERE=Path(__file__).resolve().parent
OUT=HERE/'previews';OUT.mkdir(exist_ok=True)
pr=Presentation(HERE/'Social_Relationship_Lab.pptx')
SCALE=144/914400
FONT_NORMAL='/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
FONT_BOLD='/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
env=os.environ|{'XDG_CACHE_HOME':'/private/tmp/social-slides-fontcache'}


def color(c,default='#F3F6F9'):
    try:return '#'+str(c.rgb)
    except (AttributeError,TypeError):return default


def wrap(text,font,width):
    lines=[];line=''
    for ch in text:
        if line and font.getlength(line+ch)>width:
            lines.append(line);line=''
        line+=ch
    lines.append(line)
    return lines


pdfs=[];warnings=[]
for i,slide in enumerate(pr.slides,1):
    svg=['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1920" height="1080" viewBox="0 0 1920 1080">',
         '<rect width="1920" height="1080" fill="#0C141F"/>']
    for shape in slide.shapes:
        x,y,w,h=[v*SCALE for v in (shape.left,shape.top,shape.width,shape.height)]
        if shape.shape_type==MSO_SHAPE_TYPE.PICTURE:
            b=shape.image.blob;mime=shape.image.content_type
            svg.append(f'<image x="{x}" y="{y}" width="{w}" height="{h}" xlink:href="data:{mime};base64,{base64.b64encode(b).decode()}"/>')
        elif shape.shape_type==MSO_SHAPE_TYPE.LINE:
            tf=shape._element.spPr.xfrm
            x1,x2=(x+w,x) if tf.flipH else (x,x+w)
            y1,y2=(y+h,y) if tf.flipV else (y,y+h)
            svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color(shape.line.color)}" stroke-width="{shape.line.width/12700*2}"/>')
        elif shape.shape_type==MSO_SHAPE_TYPE.AUTO_SHAPE:
            fill=color(shape.fill.fore_color)
            if shape.auto_shape_type==MSO_SHAPE.OVAL:
                svg.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}"/>')
            else:
                radius=min(w,h)*.1 if shape.auto_shape_type==MSO_SHAPE.ROUNDED_RECTANGLE else 0
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"/>')
        if shape.has_text_frame and shape.text:
            tf=shape.text_frame;rendered=[]
            for p in tf.paragraphs:
                size=(p.font.size.pt if p.font.size else 18)*2
                font=ImageFont.truetype(FONT_BOLD if p.font.bold else FONT_NORMAL,round(size))
                width=w-(tf.margin_left+tf.margin_right)*SCALE
                lines=wrap(p.text,font,width) if tf.word_wrap else [p.text]
                ascent,descent=font.getmetrics()
                for part in lines:
                    rendered.append(dict(text=part,size=size,ascent=ascent,height=size*1.2,
                        color=color(p.font.color),bold=p.font.bold,align=p.alignment))
                rendered[-1]['height']+=(p.space_after.pt if p.space_after else 0)*2
            height=sum(r['height'] for r in rendered)
            available=h-(tf.margin_top+tf.margin_bottom)*SCALE
            if height>available+16:
                warnings.append(dict(slide=i,text=shape.text,box_height=available,text_height=height))
            cursor=y+tf.margin_top*SCALE
            if tf.vertical_anchor==MSO_ANCHOR.MIDDLE:cursor=y+(h-height)/2
            for r in rendered:
                if r['align']==PP_ALIGN.CENTER:xx=x+w/2;anchor='middle'
                elif r['align']==PP_ALIGN.RIGHT:xx=x+w-tf.margin_right*SCALE;anchor='end'
                else:xx=x+tf.margin_left*SCALE;anchor='start'
                svg.append(f'<text x="{xx}" y="{cursor+r["ascent"]}" font-family="Hiragino Sans" font-size="{r["size"]}" font-weight="{600 if r["bold"] else 300}" fill="{r["color"]}" text-anchor="{anchor}">{escape(r["text"])}</text>')
                cursor+=r['height']
    svg.append('</svg>')
    path=OUT/f'slide-{i:02d}.svg';path.write_text('\n'.join(svg),encoding='utf-8')
    pdf=OUT/f'slide-{i:02d}.pdf'
    subprocess.run(['rsvg-convert','-f','pdf','-o',str(pdf),str(path)],env=env,check=True,capture_output=True)
    subprocess.run(['rsvg-convert','-f','png','-w','1920','-o',str(OUT/f'slide-{i:02d}.png'),str(path)],env=env,check=True,capture_output=True)
    pdfs.append(str(pdf))
subprocess.run(['pdfunite',*pdfs,str(HERE/'Social_Relationship_Lab.pdf')],check=True)
contact=Image.new('RGB',(1280,4*203),(23,31,43))
draw=ImageDraw.Draw(contact)
for i in range(1,14):
    image=Image.open(OUT/f'slide-{i:02d}.png').convert('RGB');image.thumbnail((310,175))
    x=((i-1)%4)*320+5;y=((i-1)//4)*203+18
    contact.paste(image,(x,y));draw.text((x,y-14),str(i),fill='white')
contact.save(OUT/'contact-sheet.jpg',quality=93)
(HERE/'layout-checks.json').write_text(json.dumps(dict(slides=len(pr.slides),renderer='PPTX geometry -> SVG -> librsvg/Pango PDF',
    text_height_warnings=warnings),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(slides=len(pr.slides),warnings=len(warnings)),indent=2))
