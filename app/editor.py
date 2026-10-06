import json,re,requests
from app.config import GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL

INSTRUCTIONS = """Você é o editor automatizado do Byte Curioso 27, jornal digital de Rondônia.
Resuma sem inventar, preserve atribuição à fonte e não transforme alegação em fato.
Classifique risk=high para acusações, denúncias, mortes não confirmadas, política eleitoral sensível,
pesquisas eleitorais, crime envolvendo pessoa identificável e conteúdo potencialmente difamatório.
Classifique risk=low para serviços, concursos, trânsito, eventos, agenda e comunicados oficiais.
Retorne APENAS JSON válido com:
headline, caption_instagram, caption_tiktok, short_script, risk, reason, hashtags.
Não peça voto, não faça propaganda eleitoral e não invente nomes, números ou fatos."""

def fallback(a):
    t=a["title"][:140]
    return {
        "headline":t.upper(),
        "caption_instagram":f"{t}\n\nFonte: {a['source']}\n\n#Rondonia #ByteCurioso27",
        "caption_tiktok":f"{t} | Fonte: {a['source']} #Rondonia #ByteCurioso27",
        "short_script":f"Notícia de Rondônia. {t}.",
        "risk":"high",
        "reason":"IA não configurada",
        "hashtags":["#Rondonia","#ByteCurioso27"]
    }

def _parse_json(txt):
    txt=re.sub(r"^\`\`\`json\s*|\s*\`\`\`$","",txt.strip(),flags=re.I|re.S)
    data=json.loads(txt)
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        raise ValueError("Resposta da IA não é um objeto JSON")
    return data

def _prepare_gemini(a):
    prompt=f"""{INSTRUCTIONS}

FONTE: {a['source']}
CATEGORIA: {a['category']}
TÍTULO: {a['title']}
RESUMO: {a.get('summary','')}
LINK: {a['url']}
"""
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload={
        "contents":[{"parts":[{"text":prompt}]}],
        "generationConfig":{"responseMimeType":"application/json","temperature":0.2}
    }
    r=requests.post(
        url,
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type":"application/json"},
        json=payload,
        timeout=60
    )
    r.raise_for_status()
    data=r.json()
    txt=data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_json(txt)

def _prepare_openai(a):
    from openai import OpenAI
    r=OpenAI(api_key=OPENAI_API_KEY).responses.create(
        model=OPENAI_MODEL,
        instructions=INSTRUCTIONS,
        input=f"FONTE: {a['source']}\nCATEGORIA: {a['category']}\nTÍTULO: {a['title']}\nRESUMO: {a.get('summary','')}\nLINK: {a['url']}"
    )
    return _parse_json(r.output_text)

def prepare(a):
    try:
        if GEMINI_API_KEY:
            return _prepare_gemini(a)
        if OPENAI_API_KEY:
            return _prepare_openai(a)
    except Exception as e:
        out=fallback(a)
        status=getattr(getattr(e,"response",None),"status_code",None)
        out["reason"]=f"Erro na IA{f' (HTTP {status})' if status else ''}. Verifique a chave/modelo do Gemini."
        return out
    return fallback(a)
