from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from io import BytesIO
import base64, requests

MEDIA_DIR="/tmp/media"
ASSET_DIR="/tmp/bytecurioso_assets"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
Path(ASSET_DIR).mkdir(parents=True, exist_ok=True)
W,H=1080,1920

def _font(size):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]:
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
SELO=_decode_asset("assets/selo_bc27.jpg.b64","selo.jpg")

def _circle_crop(path,size):
    if not path or not Path(path).exists():
        return None
    try:
        im=Image.open(path).convert("RGB").resize((size,size))
    except Exception:
        return None
    mask=Image.new("L",(size,size),0)
    md=ImageDraw.Draw(mask)
    md.ellipse((0,0,size,size),fill=255)
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

def _fit_lines(draw,text,max_width,start_size=116,min_size=54,max_lines=6):
    words=text.upper().split()
    best=[]
    for size in range(start_size,min_size-1,-4):
        f=_font(size); lines=[]; cur=""
        for word in words:
            t=(cur+" "+word).strip()
            if draw.textbbox((0,0),t,font=f)[2] <= max_width:
                cur=t
            else:
                if cur: lines.append(cur)
                cur=word
        if cur: lines.append(cur)
        best=lines
        if len(lines)<=max_lines:
            return f,lines
    return _font(min_size),best[:max_lines]

def make_poster(headline,category,article_id,image_url=""):
    orange=(255,105,0); white=(250,250,250); yellow=(255,211,0)
    img=Image.new("RGB",(W,H),(5,6,9))
    src=_download_image(image_url)

    # Full-screen blurred image backdrop when available
    if src:
        bg=_cover(src,W,H).filter(ImageFilter.GaussianBlur(18))
        shade=Image.new("RGBA",(W,H),(0,0,0,135))
        bg=bg.convert("RGBA")
        bg.alpha_composite(shade)
        img=bg.convert("RGB")

    d=ImageDraw.Draw(img)
    d.rectangle((0,0,W,34),fill=orange)
    d.rectangle((0,H-42,W,H),fill=orange)

    # Masthead
    d.rounded_rectangle((40,45,W-40,205),radius=28,fill=(7,8,12),outline=orange,width=5)
    d.text((205,78),"BYTE CURIOSO 27",font=_font(60),fill=white)
    d.rounded_rectangle((785,84,1000,170),radius=14,fill=(165,0,0))
    d.text((822,98),"NEWS",font=_font(43),fill=white)

    avatar=_circle_crop(AVATAR,125)
    if avatar:
        img.paste(avatar,(62,62),avatar)
        d.ellipse((58,58,191,191),outline=orange,width=5)

    selo=_circle_crop(SELO,125)
    if selo:
        img.paste(selo,(925-62,62),selo)

    # Main news image
    photo_top=245; photo_h=760
    if src:
        photo=_cover(src,W-90,photo_h)
        img.paste(photo,(45,photo_top))
        d=ImageDraw.Draw(img)
        d.rectangle((45,photo_top,W-45,photo_top+photo_h),outline=(255,255,255),width=3)
        grad=Image.new("RGBA",(W-90,280),(0,0,0,0))
        gd=ImageDraw.Draw(grad)
        for y in range(280):
            a=int(220*(y/279))
            gd.line((0,y,W-90,y),fill=(0,0,0,a))
        img.paste(grad,(45,photo_top+photo_h-280),grad)
    else:
        d.rounded_rectangle((45,photo_top,W-45,photo_top+photo_h),radius=28,fill=(12,13,18),outline=(110,35,0),width=4)
        d.text((170,520),"BYTE CURIOSO 27",font=_font(70),fill=orange)
        d.text((245,620),"RONDÔNIA NEWS",font=_font(62),fill=white)

    # Category ribbon
    d.polygon([(45,940),(770,940),(840,995),(770,1050),(45,1050)],fill=(155,0,0))
    cat=(category or "NOTÍCIA").upper()
    d.text((80,965),f"{cat} • RONDÔNIA",font=_font(39),fill=white)

    # Headline block
    d.rounded_rectangle((45,1080,W-45,1688),radius=34,fill=(4,5,8),outline=(100,30,0),width=4)
    f,lines=_fit_lines(d,headline,W-125,112,54,6)
    line_h=int(f.size*1.08)
    total=line_h*len(lines)
    y=1135+max(0,(500-total)//2)
    for i,line in enumerate(lines):
        color=white
        if i==1:
            color=yellow
        elif i in (0,3):
            color=orange
        bbox=d.textbbox((0,0),line,font=f)
        x=(W-(bbox[2]-bbox[0]))//2
        d.text((x,y),line,font=f,fill=color,stroke_width=3,stroke_fill=(0,0,0))
        y+=line_h

    # Footer
    d.rounded_rectangle((210,1740,870,1815),radius=28,fill=(7,8,12),outline=orange,width=4)
    d.text((305,1751),"@bytecurioso27",font=_font(41),fill=orange)
    d.text((122,1850),"INFORMAÇÃO • RONDÔNIA • TECNOLOGIA",font=_font(32),fill=white)

    path=f"{MEDIA_DIR}/post_{article_id}.jpg"
    img.save(path,quality=95)
    return path

def make_test_poster():
    return make_poster("NOVO EDITOR AUTOMÁTICO DO BYTE CURIOSO 27 ESTÁ NO AR","teste","instagram_test","")
