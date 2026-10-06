from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import os

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
W,H=1080,1350

def _font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def _fit_lines(draw, text, max_width, start_size=108, min_size=54, max_lines=5):
    words=text.upper().split()
    for size in range(start_size, min_size-1, -4):
        font=_font(size)
        lines=[]; cur=""
        for w in words:
            test=(cur+" "+w).strip()
            if draw.textbbox((0,0),test,font=font)[2] <= max_width:
                cur=test
            else:
                if cur: lines.append(cur)
                cur=w
        if cur: lines.append(cur)
        if len(lines) <= max_lines:
            return font, lines
    return _font(min_size), lines[:max_lines]

def make_poster(headline, category, article_id):
    img=Image.new("RGB",(W,H),(5,5,8))
    d=ImageDraw.Draw(img)
    orange=(255,112,0)
    white=(245,245,245)
    blue=(0,145,255)

    # cyber frame / glow
    d.rectangle((0,0,W,46),fill=orange)
    d.rectangle((0,H-82,W,H),fill=orange)
    d.rectangle((26,26,W-26,H-26),outline=(110,45,0),width=3)
    for x in range(0,W,135):
        d.line((x,0,x+220,220),fill=(55,24,0),width=3)
    for y in range(160,H,190):
        d.line((0,y,170,y+70),fill=(45,22,0),width=2)

    # top brand band
    d.rounded_rectangle((55,55,W-55,190),radius=24,fill=(12,12,18),outline=orange,width=4)
    d.text((85,80),"BYTE CURIOSO 27",font=_font(56),fill=white)
    d.text((735,91),"NEWS",font=_font(44),fill=orange)

    # mascot-like abstract silhouette + tech orb
    d.ellipse((68,235,340,507),fill=(20,20,26),outline=orange,width=7)
    d.ellipse((122,285,180,343),fill=orange)
    d.ellipse((225,285,283,343),fill=orange)
    d.arc((70,220,345,520),start=210,end=330,fill=orange,width=9)
    d.ellipse((760,240,1015,495),outline=blue,width=7)
    d.arc((775,255,1000,480),0,360,fill=orange,width=4)
    d.line((788,365,990,365),fill=blue,width=3)
    d.line((883,255,883,480),fill=blue,width=3)

    # category chip
    chip=f"NOTÍCIA • {category.upper()}"
    d.rounded_rectangle((70,545,W-70,620),radius=18,fill=(12,12,18),outline=orange,width=3)
    d.text((95,562),chip,font=_font(33),fill=orange)

    # headline
    font, lines=_fit_lines(d,headline,W-120,108,54,5)
    y=665
    for i,line in enumerate(lines):
        fill=orange if i in (0,2) else white
        bbox=d.textbbox((0,0),line,font=font)
        tw=bbox[2]-bbox[0]
        x=(W-tw)//2
        d.text((x,y),line,font=font,fill=fill,stroke_width=3,stroke_fill=(0,0,0))
        y += int(font.size*1.05)

    # footer
    d.rounded_rectangle((245,H-150,835,H-95),radius=25,fill=(10,10,14),outline=orange,width=3)
    d.text((310,H-142),"@bytecurioso27",font=_font(35),fill=orange)

    path=f"{MEDIA_DIR}/post_{article_id}.jpg"
    img.save(path,quality=94)
    return path

def make_test_poster():
    return make_poster("CONEXÃO AUTOMÁTICA COM O INSTAGRAM ATIVADA","teste","instagram_test")
