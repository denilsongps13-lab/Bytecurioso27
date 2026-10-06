from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.poster import make_test_poster,asset_status
from app import config

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True,exist_ok=True)

app=FastAPI(title="Byte Curioso 27 v2")
app.mount("/media",StaticFiles(directory=MEDIA_DIR),name="media")

@app.get("/")
def root():
    return {"ok":True,"service":"Byte Curioso 27","version":"v2","publishing":config.META_ENABLED}

@app.get("/health")
def health():
    return {"ok":True,"version":"v2","meta_enabled":config.META_ENABLED,"mascot":asset_status()}

@app.get("/preview/test.jpg")
def preview_test():
    return FileResponse(make_test_poster(),media_type="image/jpeg",headers={"Cache-Control":"no-store, max-age=0"})
