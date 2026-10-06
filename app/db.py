import hashlib,json,os,sqlite3

DATABASE_URL=os.getenv("DATABASE_URL","").strip()
SQLITE_PATH=os.getenv("SQLITE_PATH","/tmp/bytecurioso.db")

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:
    psycopg=None
    dict_row=None

USE_POSTGRES=bool(DATABASE_URL and psycopg)

def backend_name():
    return "postgres" if USE_POSTGRES else "sqlite"

def _pg():
    return psycopg.connect(DATABASE_URL,row_factory=dict_row)

def _sqlite():
    c=sqlite3.connect(SQLITE_PATH)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    if USE_POSTGRES:
        with _pg() as c:
            with c.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS articles(
                        id BIGSERIAL PRIMARY KEY,
                        fingerprint TEXT UNIQUE NOT NULL,
                        source TEXT, category TEXT, title TEXT, url TEXT,
                        summary TEXT, published TEXT, image_url TEXT, ai_json TEXT,
                        status TEXT DEFAULT 'new',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
        print("DB_BACKEND=postgres",flush=True)
        return
    with _sqlite() as c:
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
    print(f"DB_BACKEND=sqlite path={SQLITE_PATH}",flush=True)

def fp(title,url):
    return hashlib.sha256((title.strip().lower()+"|"+url.strip()).encode()).hexdigest()

def insert_article(a):
    values=(fp(a["title"],a["url"]),a["source"],a["category"],a["title"],a["url"],a.get("summary",""),a.get("published",""),a.get("image_url",""))
    if USE_POSTGRES:
        try:
            with _pg() as c:
                with c.cursor() as cur:
                    cur.execute("""INSERT INTO articles(fingerprint,source,category,title,url,summary,published,image_url)
                                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                                   ON CONFLICT(fingerprint) DO NOTHING RETURNING id""",values)
                    row=cur.fetchone()
                    return row["id"] if row else None
        except Exception as e:
            print(f"DB_INSERT_ERROR backend=postgres error={type(e).__name__}:{e}",flush=True)
            raise
    try:
        with _sqlite() as c:
            cur=c.execute("INSERT INTO articles(fingerprint,source,category,title,url,summary,published,image_url) VALUES(?,?,?,?,?,?,?,?)",values)
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def set_ai(article_id,payload):
    raw=json.dumps(payload,ensure_ascii=False)
    if USE_POSTGRES:
        with _pg() as c:
            with c.cursor() as cur:
                cur.execute("UPDATE articles SET ai_json=%s,status='prepared' WHERE id=%s",(raw,article_id))
    else:
        with _sqlite() as c:
            c.execute("UPDATE articles SET ai_json=?,status='prepared' WHERE id=?",(raw,article_id))

def set_status(article_id,status):
    if USE_POSTGRES:
        with _pg() as c:
            with c.cursor() as cur:
                cur.execute("UPDATE articles SET status=%s WHERE id=%s",(status,article_id))
    else:
        with _sqlite() as c:
            c.execute("UPDATE articles SET status=? WHERE id=?",(status,article_id))

def get_article(article_id):
    if USE_POSTGRES:
        with _pg() as c:
            with c.cursor() as cur:
                cur.execute("SELECT * FROM articles WHERE id=%s",(article_id,))
                return cur.fetchone()
    with _sqlite() as c:
        r=c.execute("SELECT * FROM articles WHERE id=?",(article_id,)).fetchone()
        return dict(r) if r else None

def pending(limit=20):
    if USE_POSTGRES:
        with _pg() as c:
            with c.cursor() as cur:
                cur.execute("SELECT * FROM articles WHERE status IN ('prepared','review') ORDER BY id DESC LIMIT %s",(limit,))
                return cur.fetchall()
    with _sqlite() as c:
        return [dict(r) for r in c.execute("SELECT * FROM articles WHERE status IN ('prepared','review') ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]

def queued_articles(limit=300):
    if USE_POSTGRES:
        with _pg() as c:
            with c.cursor() as cur:
                cur.execute("""SELECT * FROM articles WHERE status='new'
                               ORDER BY CASE WHEN published IS NULL OR published='' THEN 1 ELSE 0 END,
                               created_at DESC,id DESC LIMIT %s""",(limit,))
                return cur.fetchall()
    with _sqlite() as c:
        rows=c.execute("""SELECT * FROM articles WHERE status='new'
                          ORDER BY CASE WHEN published IS NULL OR published='' THEN 1 ELSE 0 END,
                          created_at DESC,id DESC LIMIT ?""",(limit,)).fetchall()
        return [dict(r) for r in rows]
