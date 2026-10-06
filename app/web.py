from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True,exist_ok=True)

app=FastAPI(title="Byte Curioso 27 News Bot")
app.mount("/media",StaticFiles(directory=MEDIA_DIR),name="media")

@app.get("/")
def root():
    return {"ok":True,"service":"Byte Curioso 27 News Bot"}

@app.get("/health")
def health():
    return {"ok":True}


_TEST_DONE = False

@app.get("/ops/test-layout-20261006")
def test_layout_once():
    global _TEST_DONE
    if _TEST_DONE:
        return {"ok": True, "status": "already_done"}
    from app.poster import make_poster
    from app.publishers.meta import post_instagram_image
    from app import config
    path = make_poster("BYTE CURIOSO 27 NEWS: NOVO PADRÃO VISUAL AUTOMÁTICO", "teste de layout", "layout_test")
    image_url = f"{config.PUBLIC_BASE_URL}/media/{path.split('/')[-1]}"
    result = post_instagram_image(
        image_url,
        "🧪 TESTE DE LAYOUT — Byte Curioso 27 News.\n\nEsta publicação é apenas um teste do novo padrão visual automático do robô.\n\n#ByteCurioso27 #Rondonia"
    )
    _TEST_DONE = True
    return {"ok": True, "result": result}
