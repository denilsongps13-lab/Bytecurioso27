"""JUDIT authentication-only diagnostic. No judicial query is created."""
import asyncio
import os
import json
import urllib.error
import urllib.request

def _probe():
    key = os.environ.get("JUDIT_API_KEY", "").strip()
    if not key:
        return "⚠️ JUDIT_API_KEY não configurada no Render."
    url = "https://requests.production.judit.io/requests?page_size=1"
    req = urllib.request.Request(url, headers={"api-key": key, "Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            body = exc.read(4096).decode('utf-8', errors='replace')
            payload = json.loads(body)
            detail = payload.get('message') or payload.get('detail') or payload.get('error') or '' if isinstance(payload, dict) else ''
            if not isinstance(detail, str):
                detail = ''
            detail = detail.replace(key, '[REDACTED]')[:240]
        except Exception:
            detail = ''
    except Exception:
        return "❌ Não foi possível conectar à JUDIT. Verifique rede e endpoint."
    if status == 200:
        return "✅ JUDIT respondeu HTTP 200. Chave aceita para leitura; nenhuma consulta criada."
    if status in (401, 403):
        return f"❌ JUDIT respondeu HTTP {status}. Verifique chave e permissões."
    return f"ℹ️ JUDIT respondeu HTTP {status}. {detail if detail else 'Sem detalhe legível na resposta.'} Nenhuma consulta criada."

async def judit_teste(update, context):
    await update.message.reply_text("🔐 Verificando autenticação JUDIT sem criar consultas...")
    result = await asyncio.to_thread(_probe)
    await update.message.reply_text(result)
