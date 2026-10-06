from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import math

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
W,H=1080,1920

def _font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def _fit_lines(draw,text,max_width,start_size=112,min_size=58,max_lines=6):
    words=text.upper().split()
    for size in range(start_size,min_size-1,-4):
        f=_font(size); lines=[]; cur=""
        for word in words:
            test=(cur+" "+word).strip()
            if draw.textbbox((0,0),test,font=f)[2] <= max_width:
                cur=test
            else:
                if cur: lines.append(cur)
                cur=word
        if cur: lines.append(cur)
        if len(lines) <= max_lines:
            return f,lines
    return _font(min_size),lines[:max_lines]

def _tech_background():
    img=Image.new("RGB",(W,H),(4,5,8))
    d=ImageDraw.Draw(img)
    orange=(255,105,0); blue=(0,130,255)
    for y in range(H):
        t=y/H
        r=int(8+10*(1-t)); g=int(7+5*(1-t)); b=int(10+8*t)
        d.line((0,y,W,y),fill=(r,g,b))
    for i in range(22):
        x=(i*173)%W
        d.line((x,0,(x+420)%W,H),fill=(52,22,4),width=3)
    for y in range(180,H,210):
        d.line((0,y,230,y+90),fill=(78,30,3),width=3)
        d.line((W-230,y+20,W,y+100),fill=(0,45,80),width=3)
    d.rectangle((0,0,W,34),fill=orange)
    d.rectangle((0,H-44,W,H),fill=orange)
    return img

def make_poster(headline,category,article_id):
    img=_tech_background()
    d=ImageDraw.Draw(img)
    orange=(255,105,0); white=(248,248,248); blue=(0,150,255); yellow=(255,205,0)

    # masthead, inspired by high-impact local-news cards but branded uniquely
    d.rounded_rectangle((50,55,W-50,210),radius=28,fill=(7,8,12),outline=orange,width=5)
    d.text((82,78),"BYTE",font=_font(64),fill=white)
    d.text((275,78),"CURIOSO 27",font=_font(64),fill=orange)
    d.rounded_rectangle((735,86,995,174),radius=14,fill=(170,0,0))
    d.text((770,100),"NEWS",font=_font(49),fill=white)

    # identity circles
    d.ellipse((55,260,335,540),fill=(12,12,18),outline=orange,width=8)
    d.ellipse((100,305,175,380),fill=orange)
    d.ellipse((215,305,290,380),fill=orange)
    d.arc((105,340,285,475),15,165,fill=orange,width=10)
    d.text((106,468),"BYTE",font=_font(32),fill=white)

    d.ellipse((745,260,1025,540),fill=(8,10,18),outline=blue,width=8)
    d.arc((785,300,985,500),0,360,fill=orange,width=6)
    d.line((885,300,885,500),fill=blue,width=4)
    d.line((785,400,985,400),fill=blue,width=4)
    d.text((808,462),"RONDÔNIA",font=_font(29),fill=white)

    # category ribbon
    d.polygon([(55,590),(820,590),(880,640),(820,690),(55,690)],fill=(155,0,0))
    d.text((90,612),f"{category.upper()} • RONDÔNIA",font=_font(40),fill=white)

    # headline panel
    d.rounded_rectangle((45,735,W-45,1600),radius=34,fill=(5,6,9),outline=(90,25,0),width=4)
    f,lines=_fit_lines(d,headline,W-120,118,58,6)
    line_h=int(f.size*1.08)
    total=line_h*len(lines)
    y=790+max(0,(720-total)//2)
    highlight_words={"RONDÔNIA","GOVERNO","POLÍCIA","ELEIÇÕES","JUSTIÇA","SAÚDE","TECNOLOGIA","MULHERES","ALERTA"}
    for idx,line in enumerate(lines):
        fill=white
        if idx==1 or any(w in line.split() for w in highlight_words):
            fill=yellow if idx%2 else orange
        bbox=d.textbbox((0,0),line,font=f)
        x=(W-(bbox[2]-bbox[0]))//2
        d.text((x,y),line,font=f,fill=fill,stroke_width=3,stroke_fill=(0,0,0))
        y+=line_h

    # lower branding
    d.rounded_rectangle((235,1665,845,1735),radius=28,fill=(8,8,12),outline=orange,width=4)
    d.text((302,1675),"@bytecurioso27",font=_font(40),fill=orange)
    d.text((80,1800),"INFORMAÇÃO • RONDÔNIA • TECNOLOGIA",font=_font(34),fill=white)

    path=f"{MEDIA_DIR}/post_{article_id}.jpg"
    img.save(path,quality=95)
    return path

def make_test_poster():
    return make_poster("NOVO PADRÃO VISUAL AUTOMÁTICO EM REELS","teste","instagram_test")
