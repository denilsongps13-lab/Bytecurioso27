from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.poster import make_test_poster

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

@app.get("/preview/test.jpg")
def preview_test():
    return FileResponse(make_test_poster(), media_type="image/jpeg")
