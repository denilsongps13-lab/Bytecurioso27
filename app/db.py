import sqlite3, hashlib, json

DB = "/tmp/bytecurioso.db"

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS articles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT UNIQUE,
            source TEXT, category TEXT, title TEXT, url TEXT,
            summary TEXT, published TEXT, image_url TEXT, ai_json TEXT,
            status TEXT DEFAULT 'new',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cols=[r[1] for r in c.execute("PRAGMA table_info(articles)").fetchall()]
        if "image_url" not in cols:
            c.execute("ALTER TABLE articles ADD COLUMN image_url TEXT")

def fp(title,url):
    return hashlib.sha256((title.strip().lower()+"|"+url.strip()).encode()).hexdigest()

def insert_article(a):
    try:
        with connect() as c:
            cur=c.execute("INSERT INTO articles(fingerprint,source,category,title,url,summary,published,image_url) VALUES(?,?,?,?,?,?,?,?)",
                (fp(a["title"],a["url"]),a["source"],a["category"],a["title"],a["url"],a.get("summary",""),a.get("published",""),a.get("image_url","")))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def set_ai(article_id,payload):
    with connect() as c:
        c.execute("UPDATE articles SET ai_json=?, status='prepared' WHERE id=?",(json.dumps(payload,ensure_ascii=False),article_id))

def set_status(article_id,status):
    with connect() as c:
        c.execute("UPDATE articles SET status=? WHERE id=?",(status,article_id))

def get_article(article_id):
    with connect() as c:
        r=c.execute("SELECT * FROM articles WHERE id=?",(article_id,)).fetchone()
        return dict(r) if r else None

def pending(limit=20):
    with connect() as c:
        rows=c.execute("SELECT * FROM articles WHERE status IN ('prepared','review') ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]
