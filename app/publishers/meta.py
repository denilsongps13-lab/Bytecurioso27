import time
import requests
from app import config

def _endpoint(path):
    return f"https://graph.instagram.com/{path.lstrip('/')}"

def _wait_until_ready(creation_id, timeout_seconds=90, poll_seconds=3):
    deadline=time.time()+timeout_seconds
    last={}
    while time.time() < deadline:
        r=requests.get(
            _endpoint(creation_id),
            params={
                "fields":"status_code,status",
                "access_token":config.META_ACCESS_TOKEN,
            },
            timeout=30,
        )
        r.raise_for_status()
        last=r.json()
        status=(last.get("status_code") or last.get("status") or "").upper()
        if status=="FINISHED":
            return last
        if status=="ERROR":
            raise RuntimeError(f"Instagram media processing failed: {last}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Instagram media processing timeout. Last status: {last}")

def post_instagram_image(image_url, caption):
    if not (config.META_ENABLED and config.META_ACCESS_TOKEN and config.INSTAGRAM_USER_ID):
        return {"status":"skipped","reason":"Instagram não configurado"}

    create=requests.post(
        _endpoint(f"{config.INSTAGRAM_USER_ID}/media"),
        data={
            "image_url":image_url,
            "caption":caption,
            "access_token":config.META_ACCESS_TOKEN,
        },
        timeout=60,
    )
    if not create.ok:
        raise RuntimeError(f"Instagram media create failed ({create.status_code}): {create.text[:500]}")
    cid=create.json()["id"]

    _wait_until_ready(cid)

    publish=requests.post(
        _endpoint(f"{config.INSTAGRAM_USER_ID}/media_publish"),
        data={
            "creation_id":cid,
            "access_token":config.META_ACCESS_TOKEN,
        },
        timeout=60,
    )
    if not publish.ok:
        raise RuntimeError(f"Instagram media publish failed ({publish.status_code}): {publish.text[:500]}")
    media_id=publish.json().get("id","")
    permalink=""
    if media_id:
        try:
            detail=requests.get(
                _endpoint(media_id),
                params={"fields":"id,permalink,media_type,username","access_token":config.META_ACCESS_TOKEN},
                timeout=30,
            )
            if detail.ok:
                permalink=detail.json().get("permalink","")
        except Exception:
            pass
    return {"status":"published","id":media_id,"permalink":permalink}
