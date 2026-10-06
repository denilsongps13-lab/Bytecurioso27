from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from io import BytesIO
import base64, requests, math

MEDIA_DIR="/tmp/media"
ASSET_DIR="/tmp/bytecurioso_assets"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
Path(ASSET_DIR).mkdir(parents=True, exist_ok=True)

W,H=1080,1920
BLACK=(5,7,10)
ORANGE=(255,92,0)
ORANGE2=(255,150,0)
BLUE=(0,132,255)
WHITE=(248,249,252)
SILVER=(213,218,225)
DARK=(10,12,17)
MUTED=(175,181,191)

def _font(size,bold=True):
    paths=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def _decode_asset(src_b64,out_name):
    out=Path(ASSET_DIR)/out_name
    if out.exists():
        return out
    p=Path(src_b64)
    if p.exists():
        try:
            out.write_bytes(base64.b64decode(p.read_text(encoding="utf-8")))
            return out
        except Exception:
            return None
    return None

AVATAR=_decode_asset("assets/avatar_bc27.jpg.b64","avatar.jpg")

def _download_image(url):
    if not url:
        return None
    try:
        r=requests.get(url,timeout=15,headers={"User-Agent":"Mozilla/5.0 ByteCurioso27NewsBot/1.0"})
        if not r.ok or len(r.content)<4000:
            return None
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

def _cover(im,w,h):
    scale=max(w/im.width,h/im.height)
    nw=max(1,int(im.width*scale)); nh=max(1,int(im.height*scale))
    im=im.resize((nw,nh),Image.Resampling.LANCZOS)
    left=(nw-w)//2; top=(nh-h)//2
    return im.crop((left,top,left+w,top+h))

def _avatar_panel():
    if not AVATAR or not Path(AVATAR).exists():
        return None
    try:
        im=Image.open(AVATAR).convert("RGB")
        return _cover(im,760,760)
    except Exception:
        return None

def _glow_line(base,points,fill,width=5,glow=18):
    layer=Image.new("RGBA",base.size,(0,0,0,0))
    ld=ImageDraw.Draw(layer)
    ld.line(points,fill=fill,width=width,joint="curve")
    blur=layer.filter(ImageFilter.GaussianBlur(glow))
    base.alpha_composite(blur)
    base.alpha_composite(layer)

def _fit_headline(draw,text,max_width=950,max_lines=5):
    words=" ".join((text or "BYTE CURIOSO 27").upper().split()).split()
    for size in range(94,50,-2):
        f=_font(size,True)
        lines=[]; cur=""
        for word in words:
            test=(cur+" "+word).strip()
            if draw.textbbox((0,0),test,font=f,stroke_width=1)[2] <= max_width:
                cur=test
            else:
                if cur: lines.append(cur)
                cur=word
        if cur: lines.append(cur)
        if len(lines)<=max_lines:
            return f,lines
    f=_font(50,True)
    lines=[]; cur=""
    for word in words:
        test=(cur+" "+word).strip()
        if draw.textbbox((0,0),test,font=f)[2] <= max_width:
            cur=test
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    if len(lines)>max_lines:
        lines=lines[:max_lines]
        last=lines[-1]
        while draw.textbbox((0,0),last+"…",font=f)[2] > max_width and " " in last:
            last=last.rsplit(" ",1)[0]
        lines[-1]=last+"…"
    return f,lines

def _draw_cyber_background(img):
    d=ImageDraw.Draw(img)
    d.rectangle((0,0,W,H),fill=BLACK)
    # vertical city / tech panels
    for x in range(0,W,90):
        h=180+((x*37)%360)
        d.rectangle((x,H-h,x+56,H),fill=(8,13,23))
        for y in range(H-h+20,H-20,36):
            if ((x+y)//18)%3:
                d.rectangle((x+10,y,x+42,y+10),fill=(15,45,77))
    # diagonal tech rails
    for off in range(-600,1600,180):
        d.line((off,0,off+700,H),fill=(34,25,18),width=3)
    # orange frame accents
    d.line((0,10,W,10),fill=ORANGE,width=10)
    d.line((0,H-12,W,H-12),fill=ORANGE,width=8)
    for y in (100,840,1450,1760):
        d.line((35,y,220,y),fill=ORANGE,width=5)
        d.line((860,y,1045,y),fill=ORANGE,width=5)

def make_poster(headline,category,article_id,image_url="",source=""):
    base=Image.new("RGBA",(W,H),BLACK+(255,))
    _draw_cyber_background(base)
    d=ImageDraw.Draw(base)

    # source-photo panel in the upper background when available
    news=_download_image(image_url)
    if news:
        photo=_cover(news,1080,760).convert("RGBA")
        photo.putalpha(150)
        base.alpha_composite(photo,(0,120))
        dark=Image.new("RGBA",(W,760),(0,0,0,90))
        base.alpha_composite(dark,(0,120))

    # blue/orange energy lines
    _glow_line(base,[(0,700),(190,620),(390,650),(610,590),(1080,675)],(0,135,255,255),4,16)
    _glow_line(base,[(0,760),(210,690),(420,735),(690,655),(1080,725)],(255,92,0,255),5,18)

    # mascot hero
    avatar=_avatar_panel()
    if avatar:
        av=avatar.convert("RGBA")
        mask=Image.new("L",av.size,0)
        md=ImageDraw.Draw(mask)
        md.rounded_rectangle((0,0,av.width,av.height),radius=110,fill=255)
        av.putalpha(mask)
        glow=Image.new("RGBA",av.size,(255,92,0,0))
        gd=ImageDraw.Draw(glow)
        gd.rounded_rectangle((10,10,av.width-10,av.height-10),radius=115,outline=(255,92,0,235),width=18)
        glow=glow.filter(ImageFilter.GaussianBlur(16))
        base.alpha_composite(glow,(160,90))
        base.alpha_composite(av,(160,90))

    # top logo/brand badge
    d.rounded_rectangle((670,52,1020,174),radius=46,fill=(8,10,14,235),outline=ORANGE,width=6)
    d.text((845,92),"BYTE",font=_font(38),fill=WHITE,anchor="mm")
    d.text((845,132),"CURIOSO 27",font=_font(39),fill=ORANGE2,anchor="mm")

    # category banner
    cat=(category or "NOTÍCIA").upper().replace("_"," ")
    if len(cat)>22: cat=cat[:22]
    d.rounded_rectangle((135,785,945,865),radius=24,fill=(7,9,12,245),outline=ORANGE,width=4)
    d.text((540,825),f"BYTE CURIOSO 27 NEWS  •  {cat}",font=_font(31),fill=WHITE,anchor="mm")

    # headline zone
    panel_top=900
    d.rounded_rectangle((40,panel_top,1040,1588),radius=32,fill=(4,6,9,232),outline=(255,92,0,180),width=3)

    hf,lines=_fit_headline(d,headline,900,5)
    line_h=hf.size+10
    total=len(lines)*line_h-10
    y=panel_top+55+max(0,(560-total)//2)

    # blocky headline with shadow/stroke; alternate orange and white
    for i,line in enumerate(lines):
        fill=ORANGE2 if i%3!=1 else WHITE
        bbox=d.textbbox((0,0),line,font=hf,stroke_width=2)
        tw=bbox[2]-bbox[0]
        x=(W-tw)//2
        d.text((x+5,y+7),line,font=hf,fill=(0,0,0),stroke_width=6,stroke_fill=(0,0,0))
        d.text((x,y),line,font=hf,fill=fill,stroke_width=2,stroke_fill=(104,43,0) if fill==ORANGE2 else (50,54,61))
        y+=line_h

    # Rondônia real-time rail
    d.rounded_rectangle((90,1625,990,1710),radius=26,fill=(7,9,12,245),outline=ORANGE,width=4)
    d.text((540,1668),"RONDÔNIA EM TEMPO REAL",font=_font(34),fill=WHITE,anchor="mm")

    # source + handle
    src=(source or "Fonte não informada").strip()
    if len(src)>46: src=src[:43]+"…"
    d.text((85,1755),f"FONTE: {src.upper()}",font=_font(22),fill=SILVER)
    d.rounded_rectangle((285,1810,795,1880),radius=28,fill=(7,9,12,245),outline=ORANGE,width=4)
    d.text((540,1845),"@bytecurioso27",font=_font(30),fill=ORANGE2,anchor="mm")

    out=base.convert("RGB")
    path=f"{MEDIA_DIR}/post_{article_id}.jpg"
    out.save(path,quality=92,optimize=True)
    return path

def make_test_poster():
    return make_poster(
        "GIRO DA SAÚDE AMPLIA ATENDIMENTO PARA CRIANÇAS E FAMÍLIAS EM RONDÔNIA",
        "saúde",
        "instagram_test",
        "",
        "Saúde Rondônia"
    )
