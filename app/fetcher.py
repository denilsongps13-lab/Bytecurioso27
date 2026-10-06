import feedparser, yaml, requests, re
from pathlib import Path
from app.db import insert_article

def load_sources(path="sources.yml"):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["sources"]

def _feed_image(entry):
    for key in ("media_content","media_thumbnail"):
        items=getattr(entry,key,[]) or []
        for item in items:
            if isinstance(item,dict) and item.get("url"):
                return item["url"]
    for item in getattr(entry,"enclosures",[]) or []:
        href=item.get("href") or item.get("url")
        typ=(item.get("type") or "").lower()
        if href and ("image" in typ or re.search(r"\.(jpg|jpeg|png|webp)(\?|$)",href,re.I)):
            return href
    return ""

def _og_image(url):
    try:
        r=requests.get(url,timeout=12,headers={"User-Agent":"Mozilla/5.0 ByteCurioso27NewsBot/1.0"})
        if not r.ok:
            return ""
        html=r.text[:450000]
        patterns=[
            r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)',
            r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
            r'name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)',
        ]
        for p in patterns:
            m=re.search(p,html,re.I)
            if m:
                return m.group(1).replace("&amp;","&")
    except Exception:
        pass
    return ""

def scan_sources():
    added=[]
    for s in load_sources():
        feed=feedparser.parse(s["url"])
        for e in feed.entries[:10]:
            url=getattr(e,"link","").strip()
            # Keep the bulk scan fast. Do not open every article page here.
            # The selected stories can resolve an OG image lazily before publishing.
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
    """Resolve a source image only for a story that is actually going to be published."""
    if article.get("image_url"):
        return article
    url=(article.get("url") or "").strip()
    if url:
        article["image_url"]=_og_image(url)
    return article
