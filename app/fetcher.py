import feedparser, yaml
from pathlib import Path
from app.db import insert_article

def load_sources(path="sources.yml"):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["sources"]

def scan_sources():
    added=[]
    for s in load_sources():
        feed=feedparser.parse(s["url"])
        for e in feed.entries[:10]:
            a={"source":s["name"],"category":s.get("category","geral"),
               "title":getattr(e,"title","").strip(),"url":getattr(e,"link","").strip(),
               "summary":getattr(e,"summary","")[:2000],"published":getattr(e,"published","")}
            if a["title"] and a["url"]:
                aid=insert_article(a)
                if aid:
                    a["id"]=aid
                    added.append(a)
    return added
