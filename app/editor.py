import json,re
from openai import OpenAI
from app.config import OPENAI_API_KEY, OPENAI_MODEL

INSTRUCTIONS = """Você é o editor automatizado do Byte Curioso 27, jornal digital de Rondônia.
Resuma sem inventar, preserve atribuição à fonte e não transforme alegação em fato.
Classifique risk=high para acusações, denúncias, mortes não confirmadas, política eleitoral sensível,
pesquisas eleitorais, crime envolvendo pessoa identificável e conteúdo potencialmente difamatório.
Classifique risk=low para serviços, concursos, trânsito, eventos, agenda e comunicados oficiais.
Retorne APENAS JSON com headline, caption_instagram, caption_tiktok, short_script, risk, reason, hashtags."""

def fallback(a):
    t=a["title"][:140]
    return {"headline":t.upper(),"caption_instagram":f"{t}\n\nFonte: {a['source']}\n\n#Rondonia #ByteCurioso27",
    "caption_tiktok":f"{t} | Fonte: {a['source']} #Rondonia #ByteCurioso27",
    "short_script":f"Notícia de Rondônia. {t}.","risk":"high","reason":"IA não configurada","hashtags":["#Rondonia","#ByteCurioso27"]}

def prepare(a):
    if not OPENAI_API_KEY: return fallback(a)
    r=OpenAI(api_key=OPENAI_API_KEY).responses.create(
        model=OPENAI_MODEL,instructions=INSTRUCTIONS,
        input=f"FONTE: {a['source']}\nCATEGORIA: {a['category']}\nTÍTULO: {a['title']}\nRESUMO: {a.get('summary','')}\nLINK: {a['url']}")
    txt=re.sub(r"^\`\`\`json\s*|\s*\`\`\`$","",r.output_text.strip(),flags=re.I|re.S)
    try: return json.loads(txt)
    except: return fallback(a)
