from fastapi import FastAPI

app = FastAPI(title="Byte Curioso 27 News Bot")

@app.get("/")
def root():
    return {"ok": True, "service": "Byte Curioso 27 News Bot"}

@app.get("/health")
def health():
    return {"ok": True}
