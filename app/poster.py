from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap, os

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
W,H=1080,1350

def _font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def _wrap(draw,text,font,maxw):
    words=text.split()
    lines=[]; cur=""
    for word in words:
        t=(cur+" "+word).strip()
        if draw.textbbox((0,0),t,font=font)[2] <= maxw:
            cur=t
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    return lines[:7]

def make_poster(headline, category, article_id):
    img=Image.new("RGB",(W,H),(7,7,9))
    d=ImageDraw.Draw(img)
    orange=(255,112,0)
    d.rectangle((0,0,W,38),fill=orange)
    d.rectangle((0,H-74,W,H),fill=orange)
    d.text((58,68),"BYTE CURIOSO 27",font=_font(64),fill=(255,135,25))
    d.text((60,150),"RONDÔNIA • NOTÍCIAS",font=_font(31),fill=(235,235,235))
    d.rectangle((58,220,W-58,228),fill=orange)
    f=_font(88); y=315
    for i,line in enumerate(_wrap(d,headline.upper(),f,W-116)):
        d.text((58,y),line,font=f,fill=orange if i%2==0 else (245,245,245),
               stroke_width=2,stroke_fill=(0,0,0))
        y += 108
    d.text((60,H-170),f"CATEGORIA: {category.upper()}",font=_font(30),fill=(200,200,200))
    d.text((58,H-58),"@bytecurioso27",font=_font(36),fill=(10,10,10))
    path=f"{MEDIA_DIR}/post_{article_id}.jpg"
    img.save(path,quality=94)
    return path

def make_test_poster():
    img=Image.new("RGB",(W,H),(7,7,9))
    d=ImageDraw.Draw(img)
    orange=(255,112,0)
    d.rectangle((0,0,W,40),fill=orange)
    d.text((70,130),"BYTE CURIOSO 27",font=_font(72),fill=orange)
    d.text((70,310),"CONEXÃO",font=_font(120),fill=(245,245,245))
    d.text((70,445),"AUTOMÁTICA",font=_font(115),fill=orange)
    d.text((70,650),"TESTE DO SISTEMA",font=_font(68),fill=(245,245,245))
    d.text((70,760),"Instagram conectado ao robô",font=_font(42),fill=(200,200,200))
    d.rectangle((0,H-78,W,H),fill=orange)
    d.text((70,H-62),"@bytecurioso27",font=_font(38),fill=(10,10,10))
    path=f"{MEDIA_DIR}/instagram_test.jpg"
    img.save(path,quality=94)
    return path
