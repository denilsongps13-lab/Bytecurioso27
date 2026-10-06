import feedparser, yaml, requests, re, html as html_lib
from pathlib import Path
from urllib.parse import urljoin, urlparse
from app.db import insert_article

UA={"User-Agent":"Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/125 Safari/537.36 ByteCurioso27/1.0"}

def load_sources(path="sources.yml"):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["sources"]

def _valid_image_url(url):
    return bool(url and url.startswith(("http://","https://")))

def _html_image(raw):
    raw=raw or ""
    patterns=[
        r'<img[^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+data-src=["\']([^"\']+)["\']',
    ]
    for p in patterns:
        m=re.search(p,raw,re.I)
        if m:
            u=html_lib.unescape(m.group(1))
            if _valid_image_url(u):
                return u
    return ""

def _feed_image(entry):
    for key in ("media_content","media_thumbnail"):
        items=getattr(entry,key,[]) or []
        for item in items:
            if isinstance(item,dict) and _valid_image_url(item.get("url","")):
                return item["url"]
    for item in getattr(entry,"enclosures",[]) or []:
        href=item.get("href") or item.get("url")
        typ=(item.get("type") or "").lower()
        if _valid_image_url(href) and ("image" in typ or re.search(r"\.(jpg|jpeg|png|webp)(\?|$)",href,re.I)):
            return href
    img=_html_image(getattr(entry,"summary",""))
    if img:
        return img
    for c in getattr(entry,"content",[]) or []:
        if isinstance(c,dict):
            img=_html_image(c.get("value",""))
            if img:
                return img
    return ""

def _resolve_article_url(url):
    if not url:
        return ""
    try:
        r=requests.get(url,timeout=15,headers=UA,allow_redirects=True)
        final=r.url
        host=(urlparse(final).hostname or "").lower()
        if "google." not in host and "news.google." not in host:
            return final
        body=r.text[:600000]
        links=re.findall(r'href=["\'](https?://[^"\']+)["\']',body,re.I)
        for link in links:
            h=(urlparse(link).hostname or "").lower()
            if h and "google." not in h and "gstatic." not in h and "googleusercontent." not in h:
                return html_lib.unescape(link)
    except Exception:
        pass
    return url

def _og_image(url):
    if not url:
        return ""
    try:
        resolved=_resolve_article_url(url)
        r=requests.get(resolved,timeout=15,headers=UA,allow_redirects=True)
        if not r.ok:
            return ""
        body=r.text[:650000]
        patterns=[
            r'property=["\']og:image(?::secure_url)?["\'][^>]*content=["\']([^"\']+)',
            r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image(?::secure_url)?["\']',
            r'name=["\']twitter:image(?::src)?["\'][^>]*content=["\']([^"\']+)',
            r'content=["\']([^"\']+)["\'][^>]*name=["\']twitter:image(?::src)?["\']',
        ]
        for p in patterns:
            m=re.search(p,body,re.I)
            if m:
                u=html_lib.unescape(m.group(1))
                u=urljoin(r.url,u)
                if _valid_image_url(u):
                    return u
        return _html_image(body)
    except Exception:
        return ""

def scan_sources():
    added=[]
    for s in load_sources():
        feed=feedparser.parse(s["url"])
        for e in feed.entries[:10]:
            url=getattr(e,"link","").strip()
            image_url=_feed_image(e)
            a={
                "source":s["name"],
                "category":s.get("category","geral"),
                "title":getattr(e,"title","").strip(),
                "url":url,
                "summary":getattr(e,"summary","")[:2000],
                "published":getattr(e,"published",""),
                "image_url":image_url,
            }
            if a["title"] and a["url"]:
                aid=insert_article(a)
                if aid:
                    a["id"]=aid
                    added.append(a)
    return added

def enrich_image(article):
    """Resolve an image only for a story selected for the current cycle."""
    if article.get("image_url"):
        return article
    article["image_url"]=_html_image(article.get("summary",""))
    if article["image_url"]:
        return article
    url=(article.get("url") or "").strip()
    if url:
        article["image_url"]=_og_image(url)
    return article
