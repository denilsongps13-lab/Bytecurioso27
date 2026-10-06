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
