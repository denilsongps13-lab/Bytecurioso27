import feedparser, yaml, requests, re, html as html_lib, logging
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.db import insert_article, update_image

log=logging.getLogger(__name__)
UA={'User-Agent':'Mozilla/5.0 ByteCurioso27News/3.0'}

def load_sources(path=None):
    path=Path(path) if path else Path(__file__).resolve().parents[1]/'sources.yml'
    return yaml.safe_load(path.read_text(encoding='utf-8'))['sources']

def _valid_image_url(url):
    return bool(url and url.startswith(('http://','https://')))

def _html_images(raw,base=''):
    soup=BeautifulSoup(raw or '', 'html.parser')
    for tag in soup.find_all('img'):
        url=tag.get('data-src') or tag.get('data-lazy-src') or tag.get('src')
        if not url and tag.get('srcset'): url=tag['srcset'].split(',')[-1].strip().split()[0]
        if not url: continue
        url=urljoin(base,html_lib.unescape(url))
        if _valid_image_url(url) and not re.search(r'(favicon|logo|avatar|pixel|tracking|spinner|\.svg(?:\?|$))',url,re.I):
            yield url

def _html_image(raw,base=''):
    return next(_html_images(raw,base),'')

def _feed_image(entry):
    for key in ('media_content','media_thumbnail','enclosures'):
        for item in entry.get(key,[]) or []:
            u=item.get('url') or item.get('href','')
            typ=item.get('type','')
            if _valid_image_url(u) and ('video' not in typ): return u
    for raw in [entry.get('summary','')]+[c.get('value','') for c in entry.get('content',[])]:
        u=_html_image(raw,entry.get('link',''))
        if u: return u
    return ''

def _resolve_article_url(url):
    if (urlparse(url).hostname or '')=='news.google.com':
        try:
            from googlenewsdecoder import gnewsdecoder
            result=gnewsdecoder(url,timeout=10.0)
            decoded=result.get('decoded_url','')
            if (result.get('success') or result.get('status')) and _valid_image_url(decoded):
                print('ARTICLE_URL_RESOLVED publisher='+str(urlparse(decoded).hostname),flush=True)
                return decoded
        except Exception as e:
            log.warning('ARTICLE_URL_RESOLVE_ERROR %s',type(e).__name__)
        return url
    return url

def _page_candidates(url):
    with requests.get(url,headers=UA,timeout=(5,12),stream=True) as r:
        r.raise_for_status(); body=bytearray()
        for chunk in r.iter_content(65536):
            body.extend(chunk)
            if len(body)>=900000: break
        soup=BeautifulSoup(body.decode(r.encoding or 'utf-8',errors='replace'),'html.parser')
        urls=[]
        for key in ('og:image:secure_url','og:image','twitter:image','twitter:image:src'):
            for tag in soup.find_all('meta'):
                if (tag.get('property') or tag.get('name') or '').lower()==key:
                    u=urljoin(r.url,html_lib.unescape(tag.get('content','')))
                    if _valid_image_url(u): urls.append(u)
        article=soup.find('article') or soup.find('main') or soup
        urls.extend(_html_images(str(article),r.url))
        return list(dict.fromkeys(urls))[:8]

def _usable_image(url):
    # Validate actual pixels, not just a URL or HTTP status.
    from app.poster import _download_image
    im=_download_image(url)
    return im is not None

def scan_sources():
    added=[]
    for s in load_sources():
        try:
            r=requests.get(s['url'],headers=UA,timeout=(5,15));r.raise_for_status()
            feed=feedparser.parse(r.content)
            for e in feed.entries[:10]:
                source=e.get('source',{}).get('title') or s['name']
                a={'source':source,'category':s.get('category','geral'),'title':e.get('title','').strip(),'url':e.get('link','').strip(),'summary':e.get('summary','')[:2000],'published':e.get('published',''),'image_url':_feed_image(e)}
                if a['title'] and a['url']:
                    aid=insert_article(a)
                    if aid: a['id']=aid;added.append(a)
        except Exception as e:
            log.warning('SOURCE_ERROR source=%s error=%s',s['name'],type(e).__name__)
    return added

def enrich_image(article):
    article=dict(article);candidates=[]
    if article.get('image_url'): candidates.append(article['image_url'])
    candidates.extend(_html_images(article.get('summary',''),article.get('url','')))
    resolved=_resolve_article_url(article.get('url',''))
    article['resolved_url']=resolved  # Keep stored URL stable for fingerprints.
    if resolved and urlparse(resolved).hostname!='news.google.com':
        try: candidates.extend(_page_candidates(resolved))
        except Exception as e: log.warning('IMAGE_PAGE_ERROR %s',type(e).__name__)
    article['image_url']=''
    for url in dict.fromkeys(candidates):
        if _usable_image(url): article['image_url']=url;break
    if article.get('id'): update_image(article['id'],article['image_url'])
    if not article['image_url']: print('IMAGE_FALLBACK thematic_layout=True',flush=True)
    return article
