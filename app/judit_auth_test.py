"""Read-only JUDIT authentication diagnostic; never creates a judicial query."""
import asyncio
import json
import os
import urllib.error
import urllib.request

URL = "https://requests.production.judit.io/requests?page=1&page_size=1"


def _safe_detail(raw, key):
    """Only expose a short, sanitized API error explanation."""
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            detail = next((payload[k] for k in ("message", "detail", "error", "errors", "title") if payload.get(k)), "")
        else:
            detail = ""
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail, ensure_ascii=False)
        if not isinstance(detail, str):
            detail = ""
    except (ValueError, TypeError):
        detail = raw if raw.lstrip().startswith(("Error", "Bad Request", "Unauthorized", "Forbidden")) else ""
    # Never return raw bodies, headers, URLs, or secrets in full.
    detail = detail.replace(key, "[REDACTED]")
    import re
    detail = re.sub(r"(?i)(api[-_ ]?key|authorization|token|secret)\s*[:=]\s*[^\s,;}]+", r"\1=[REDACTED]", detail)
    detail = re.sub(r"[\r\n\t]+", " ", detail)
    return detail[:240]


def _probe():
    key = os.environ.get("JUDIT_API_KEY", "").strip()
    if not key:
        return "⚠️ JUDIT_API_KEY não configurada no Render."
    request = urllib.request.Request(
        URL,
        headers={"api-key": key, "Accept": "application/json", "Content-Type": "application/json"},
        method="GET",
    )
    detail = ""
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            detail = _safe_detail(exc.read(4096).decode("utf-8", errors="replace"), key)
        except Exception:
            detail = ""
    except Exception:
        return "❌ Falha de conexão com a JUDIT; nenhuma consulta criada."
    if status == 200:
        return "✅ JUDIT respondeu HTTP 200. Chave aceita para leitura; nenhuma consulta criada."
    if status in (401, 403):
        return f"❌ JUDIT respondeu HTTP {status}. Verifique chave e permissões. Nenhuma consulta criada."
    explanation = detail or "Sem detalhe legível na resposta."
    return f"ℹ️ JUDIT respondeu HTTP {status}. {explanation} Nenhuma consulta criada."


async def judit_teste(update, context):
    await update.message.reply_text("🔐 Verificando autenticação JUDIT sem criar consultas...")
    result = await asyncio.to_thread(_probe)
    await update.message.reply_text(result)
