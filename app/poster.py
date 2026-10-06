"""Render the verified original brand artwork; asset failure blocks output."""
from pathlib import Path
from io import BytesIO
import hashlib, logging, re, unicodedata
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / 'assets' / 'brand_master.png'
MASTER_SHA = 'e77e8f5723209acf4fefca4dd57dc397a0e66b36c175d4249369aa1fac7797f0'
MEDIA_DIR = '/tmp/media'
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
W, H = 1080, 1920
ORANGE = (255, 132, 12)
BLUE = (22, 168, 255)
WHITE = (248, 249, 252)
CATEGORIES = {'geral':'GERAL','cidades':'CIDADES','economia':'ECONOMIA','saude':'SAÚDE','tecnologia':'TECNOLOGIA','ia':'IA','seguranca':'SEGURANÇA','policia':'POLÍCIA','politica':'POLÍTICA','eleicoes':'ELEIÇÕES','justica':'JUSTIÇA','educacao':'EDUCAÇÃO','empregos':'EMPREGOS','agronegocio':'AGRONEGÓCIO','meio_ambiente':'MEIO AMBIENTE','clima':'CLIMA','esportes':'ESPORTES','oficial':'CIDADES','transito':'CIDADES','concursos':'EMPREGOS','eventos':'CIDADES'}

def category_key(category):
    return ''.join(c for c in unicodedata.normalize('NFKD', category or 'geral') if not unicodedata.combining(c)).lower().replace(' ', '_')

def _font(size, bold=True):
    for path in ['/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        if Path(path).exists(): return ImageFont.truetype(path, size)
    raise RuntimeError('POSTER_ERROR required_font_missing')

def _master():
    raw = MASTER.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MASTER_SHA:
        raise RuntimeError('AVATAR_ERROR checksum_mismatch')
    with Image.open(BytesIO(raw)) as im:
        im.verify()
    with Image.open(BytesIO(raw)) as im:
        im.load()
        if im.width < 720 or im.height < 1280: raise RuntimeError('AVATAR_ERROR resolution_too_small')
        result = im.convert('RGB').resize((W,H), Image.Resampling.LANCZOS)
    print(f'AVATAR_OK file=assets/brand_master.png bytes={len(raw)} size={W}x{H} sha={MASTER_SHA[:12]}', flush=True)
    return result

def asset_status():
    try:
        _master()
        return {'avatar_ok':True,'width':W,'height':H,'asset':'brand_master.png','sha256':MASTER_SHA}
    except Exception as e:
        log.error('AVATAR_ERROR %s', type(e).__name__)
        return {'avatar_ok':False,'error':type(e).__name__}

def _download_image(url):
    if not url: return None
    try:
        with requests.get(url, timeout=(5,12), stream=True, headers={'User-Agent':'Mozilla/5.0'}) as r:
            r.raise_for_status()
            data = bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data)>8_000_000: raise ValueError('image_too_large')
        with Image.open(BytesIO(data)) as im:
            if im.width<300 or im.height<180 or im.width*im.height>20_000_000: return None
            im.load()
            return im.convert('RGB')
    except Exception:
        return None

def _lines(draw, text, font, width):
    lines=[]; current=''
    for word in text.split():
        # Long tokens must also fit instead of silently clipping.
        if draw.textlength(word,font=font)>width: return None
        test=(current+' '+word).strip()
        if draw.textlength(test,font=font)>width:
            lines.append(current); current=word
        else: current=test
    if current: lines.append(current)
    return lines

def _fit(draw, text, width, height, max_size=86, min_size=24):
    for size in range(max_size,min_size-1,-2):
        font=_font(size); lines=_lines(draw,text,font,width)
        if lines and len(lines)*(size+12)<=height: return font,lines
    raise ValueError('POSTER_ERROR title_cannot_fit')

def _theme(draw, key, x=785, y=660):
    # Generic icons illustrate the category and make no claims about the story.
    draw.rounded_rectangle((x-18,y-18,x+230,y+210),radius=24,fill=(4,13,23),outline=BLUE,width=3)
    if key=='saude':
        draw.rectangle((x+65,y+15,x+115,y+175),fill=BLUE)
        draw.rectangle((x+10,y+70,x+170,y+120),fill=BLUE)
    elif key in {'economia','empregos'}:
        for i,h in enumerate([55,95,140]): draw.rectangle((x+20+i*55,y+175-h,x+52+i*55,y+175),fill=BLUE)
        draw.line((x+10,y+65,x+80,y+35,x+140,y+45,x+190,y+10),fill=ORANGE,width=6)
    elif key in {'eleicoes','politica','justica'}:
        draw.rounded_rectangle((x+5,y+45,x+195,y+170),radius=10,outline=BLUE,width=6)
        draw.rectangle((x+30,y+65,x+110,y+140),outline=WHITE,width=3)
        for i in range(3):
            for j in range(3): draw.rectangle((x+132+i*18,y+74+j*22,x+142+i*18,y+84+j*22),fill=ORANGE)
        draw.line((x+55,y+20,x+145,y+20),fill=WHITE,width=6)
    elif key in {'seguranca','policia'}:
        draw.polygon([(x+95,y+5),(x+180,y+40),(x+165,y+135),(x+95,y+190),(x+25,y+135),(x+10,y+40)],outline=BLUE,width=7)
        draw.line((x+55,y+95,x+85,y+125,x+140,y+65),fill=ORANGE,width=8)
    elif key in {'meio_ambiente','clima','agronegocio'}:
        draw.ellipse((x+20,y+20,x+180,y+160),outline=BLUE,width=6)
        draw.line((x+100,y+50,x+100,y+185),fill=ORANGE,width=6)
        draw.line((x+55,y+90,x+100,y+120,x+145,y+80),fill=ORANGE,width=5)
    elif key=='esportes':
        draw.ellipse((x+25,y+20,x+185,y+180),outline=BLUE,width=6)
        draw.polygon([(x+105,y+55),(x+140,y+85),(x+128,y+130),(x+80,y+130),(x+68,y+85)],outline=ORANGE,width=5)
    else:
        draw.rounded_rectangle((x+10,y+25,x+190,y+150),radius=12,outline=BLUE,width=6)
        for i in range(3): draw.line((x+35,y+55+i*30,x+165,y+55+i*30),fill=ORANGE,width=4)
        draw.line((x+100,y+150,x+100,y+180),fill=BLUE,width=6)
        draw.line((x+60,y+180,x+140,y+180),fill=BLUE,width=6)

def make_poster(headline,category,article_id,image_url='',source=''):
    # Never use fixed example news or a fake missing-mascot placeholder.
    base=_master()
    key=category_key(category); d=ImageDraw.Draw(base)
    photo=_download_image(image_url)
    if photo:
        photo=ImageOps.fit(photo,(248,228),method=Image.Resampling.LANCZOS)
        base.paste(photo,(767,642))
        d.rounded_rectangle((767,642,1015,870),radius=12,outline=BLUE,width=4)
    else: _theme(d,key)
    d.rounded_rectangle((65,988,1015,1065),radius=18,fill=(4,10,18),outline=ORANGE,width=3)
    label='RONDÔNIA NEWS  •  '+CATEGORIES.get(key,(category or 'GERAL').upper())
    font,lines=_fit(d,label,910,65,36,18)
    d.text((W//2,1027),label,font=font,fill=WHITE,anchor='mm')
    from app.editor import public_title
    text=' '.join(public_title({'title':headline or '', 'source':source}).split()).upper()
    if not text: raise ValueError('POSTER_ERROR empty_headline')
    font,lines=_fit(d,text,910,570)
    y=1110+(570-len(lines)*(font.size+12))//2
    for i,line in enumerate(lines):
        d.text((W//2,y),line,font=font,fill=ORANGE if i%2==0 else WHITE,anchor='mt',stroke_width=2,stroke_fill=(0,0,0))
        y+=font.size+12
    d.text((W//2,1855),'BYTE CURIOSO 27 NEWS',font=_font(24),fill=WHITE,anchor='mm',stroke_width=1,stroke_fill=(0,0,0))
    safe=re.sub(r'[^A-Za-z0-9_-]','_',str(article_id))
    path=Path(MEDIA_DIR)/f'post_{safe}.jpg'; tmp=path.with_suffix('.tmp')
    base.save(tmp,format='JPEG',quality=93,optimize=True); tmp.replace(path)
    print(f'POSTER_OK id={safe} avatar=True source_image={bool(photo)} category={key}',flush=True)
    return str(path)

def make_test_poster():
    return make_poster('TESTE VISUAL DO BYTE CURIOSO 27','tecnologia','visual_test_v3',source='Teste de layout — sem publicação')
