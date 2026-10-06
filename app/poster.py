from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from io import BytesIO
import base64, requests

MEDIA_DIR="/tmp/media"
ASSET_DIR="/tmp/bytecurioso_assets"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
Path(ASSET_DIR).mkdir(parents=True, exist_ok=True)
W,H=1080,1920

BG=(8,9,12)
PANEL=(12,13,17)
ORANGE=(255,98,0)
WHITE=(248,249,251)
MUTED=(183,188,197)
LINE=(47,50,58)

def _font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def _decode_asset(src_b64, out_name):
    out=Path(ASSET_DIR)/out_name
    if out.exists():
        return out
    p=Path(src_b64)
    if p.exists():
        try:
            out.write_bytes(base64.b64decode(p.read_text(encoding="utf-8")))
            return out
        except Exception:
            pass
    return None

AVATAR=_decode_asset("assets/avatar_bc27.jpg.b64","avatar.jpg")

def _circle_crop(path,size):
    if not path or not Path(path).exists():
        return None
    try:
        im=Image.open(path).convert("RGB").resize((size,size),Image.Resampling.LANCZOS)
    except Exception:
        return None
    mask=Image.new("L",(size,size),0)
    ImageDraw.Draw(mask).ellipse((0,0,size,size),fill=255)
    out=Image.new("RGBA",(size,size),(0,0,0,0))
    out.paste(im,(0,0),mask)
    return out

def _download_image(url):
    if not url:
        return None
    try:
        r=requests.get(url,timeout=15,headers={"User-Agent":"Mozilla/5.0 ByteCurioso27NewsBot/1.0"})
        if not r.ok or len(r.content)<5000:
            return None
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

def _cover(im,w,h):
    if im is None:
        return None
    scale=max(w/im.width,h/im.height)
    nw=max(1,int(im.width*scale)); nh=max(1,int(im.height*scale))
    im=im.resize((nw,nh),Image.Resampling.LANCZOS)
    left=(nw-w)//2; top=(nh-h)//2
    return im.crop((left,top,left+w,top+h))

def _fit_lines(draw,text,max_width,start_size=82,min_size=50,max_lines=5):
    words=" ".join((text or "BYTE CURIOSO 27").upper().split()).split()
    for size in range(start_size,min_size-1,-2):
        f=_font(size,True)
        lines=[]; cur=""
        for word in words:
            test=(cur+" "+word).strip()
            if draw.textbbox((0,0),test,font=f)[2] <= max_width:
                cur=test
            else:
                if cur: lines.append(cur)
                cur=word
        if cur: lines.append(cur)
        if len(lines)<=max_lines:
            return f,lines
    f=_font(min_size,True)
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

def _text_center_y(draw, lines, font, top, bottom, gap=8):
    line_h=font.size+gap
    total=len(lines)*line_h-gap
    return top + max(0,(bottom-top-total)//2), line_h

def make_poster(headline,category,article_id,image_url="",source=""):
    img=Image.new("RGB",(W,H),BG)
    src=_download_image(image_url)

    # Hero photo
    hero_h=1110
    if src:
        hero=_cover(src,W,hero_h)
        img.paste(hero,(0,0))
    else:
        d=ImageDraw.Draw(img)
        d.rectangle((0,0,W,hero_h),fill=(24,29,36))
        d.text((W//2,510),"BYTE CURIOSO 27",font=_font(58),fill=(100,105,114),anchor="mm")

    # Dark fade from photo into headline area
    fade=Image.new("RGBA",(W,520),(0,0,0,0))
    fd=ImageDraw.Draw(fade)
    for y in range(520):
        a=int(245*(y/519))
        fd.line((0,y,W,y),fill=(8,9,12,a))
    img.paste(fade,(0,650),fade)
    d=ImageDraw.Draw(img)

    # Brand header
    d.rounded_rectangle((54,52,1026,160),radius=28,fill=(9,10,14),outline=(70,72,78),width=2)
    avatar=_circle_crop(AVATAR,68)
    if avatar:
        img.paste(avatar,(76,72),avatar)
        d.ellipse((73,69,147,143),outline=ORANGE,width=3)
    else:
        d.rounded_rectangle((74,72,142,140),radius=18,fill=ORANGE)
        d.text((108,106),"BC",font=_font(24),fill=(20,20,22),anchor="mm")

    d.text((165,73),"BYTE CURIOSO 27",font=_font(38),fill=WHITE)
    d.text((166,117),"RONDÔNIA EM TEMPO REAL",font=_font(18),fill=MUTED)

    cat=(category or "NOTÍCIA").upper().replace("_"," ")
    if len(cat)>16: cat=cat[:16]
    cat_font=_font(22)
    cw=d.textbbox((0,0),cat,font=cat_font)[2]
    chip_w=max(180,cw+54)
    x2=998; x1=x2-chip_w
    d.rounded_rectangle((x1,76,x2,138),radius=18,fill=ORANGE)
    d.text(((x1+x2)//2,107),cat,font=cat_font,fill=(20,20,22),anchor="mm")

    # Editorial panel
    panel_top=1030
    panel_bottom=1685
    d.rounded_rectangle((54,panel_top,1026,panel_bottom),radius=34,fill=PANEL,outline=LINE,width=2)
    d.rounded_rectangle((54,panel_top,68,panel_bottom),radius=7,fill=ORANGE)

    d.text((108,1074),"AGORA EM RONDÔNIA",font=_font(25),fill=ORANGE)
    d.line((108,1122,972,1122),fill=LINE,width=2)

    title_font, lines=_fit_lines(d,headline,864,82,50,5)
    y,line_h=_text_center_y(d,lines,title_font,1160,1535,10)
    for line in lines:
        d.text((108,y),line,font=title_font,fill=WHITE)
        y+=line_h

    src_label=(source or "Fonte não informada").strip()
    if len(src_label)>58: src_label=src_label[:55]+"…"
    d.text((108,1588),f"FONTE: {src_label.upper()}",font=_font(22),fill=MUTED)

    # Footer in Reels-safe zone
    d.rounded_rectangle((54,1730,1026,1820),radius=24,fill=(16,18,23))
    d.text((91,1758),"NOTÍCIAS • POLÍTICA • SEGURANÇA • TECNOLOGIA",font=_font(21),fill=(205,208,214))
    d.text((785,1850),"@bytecurioso27",font=_font(28),fill=ORANGE)

    # Small visual accents
    d.rectangle((0,0,W,10),fill=ORANGE)
    d.rounded_rectangle((54,1851,735,1895),radius=18,fill=(14,15,19))
    d.text((75,1862),"INFORMAÇÃO LOCAL, RÁPIDA E DIRETA",font=_font(18),fill=MUTED)

    path=f"{MEDIA_DIR}/post_{article_id}.jpg"
    img.save(path,quality=94,optimize=True)
    return path

def make_test_poster():
    return make_poster(
        "NOVO VISUAL DO BYTE CURIOSO 27 ESTÁ PRONTO PARA AS NOTÍCIAS",
        "teste",
        "instagram_test",
        "",
        "Byte Curioso 27"
    )
