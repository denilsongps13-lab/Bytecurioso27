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


def post_instagram_reel(video_url, caption):
    if not (config.META_ENABLED and config.META_ACCESS_TOKEN and config.INSTAGRAM_USER_ID):
        return {"status":"skipped","reason":"Instagram não configurado"}

    create=requests.post(
        _endpoint(f"{config.INSTAGRAM_USER_ID}/media"),
        data={
            "media_type":"REELS",
            "video_url":video_url,
            "caption":caption,
            "share_to_feed":"true",
            "access_token":config.META_ACCESS_TOKEN,
        },
        timeout=60,
    )
    if not create.ok:
        raise RuntimeError(f"Instagram Reel create failed ({create.status_code}): {create.text[:500]}")
    cid=create.json()["id"]

    _wait_until_ready(cid, timeout_seconds=180, poll_seconds=4)

    publish=requests.post(
        _endpoint(f"{config.INSTAGRAM_USER_ID}/media_publish"),
        data={
            "creation_id":cid,
            "access_token":config.META_ACCESS_TOKEN,
        },
        timeout=60,
    )
    if not publish.ok:
        raise RuntimeError(f"Instagram Reel publish failed ({publish.status_code}): {publish.text[:500]}")

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


def recent_marker_exists(marker, max_pages=5):
    """Use recent Instagram captions as a durable publication ledger."""
    if not (marker and config.META_ACCESS_TOKEN and config.INSTAGRAM_USER_ID):
        return False
    url=_endpoint(f"{config.INSTAGRAM_USER_ID}/media")
    params={
        "fields":"id,caption,timestamp",
        "limit":"100",
        "access_token":config.META_ACCESS_TOKEN,
    }
    try:
        for _ in range(max_pages):
            r=requests.get(url,params=params,timeout=30)
            if not r.ok:
                raise RuntimeError("META_DUPLICATE_CHECK_FAILED")
            payload=r.json()
            for item in payload.get("data",[]) or []:
                if marker in (item.get("caption") or ""):
                    return True
            nxt=(payload.get("paging") or {}).get("next")
            if not nxt:
                break
            url=nxt
            params=None
    except Exception as e:
        raise RuntimeError("META_DUPLICATE_CHECK_FAILED") from e
    return False


def check_instagram_connection():
    if not (config.META_ACCESS_TOKEN and config.INSTAGRAM_USER_ID):
        return {"ok":False,"reason":"credenciais_ausentes"}
    r=requests.get(
        _endpoint(config.INSTAGRAM_USER_ID),
        params={"fields":"id,username,account_type","access_token":config.META_ACCESS_TOKEN},
        timeout=30,
    )
    if not r.ok:
        return {"ok":False,"status_code":r.status_code,"error":r.text[:300]}
    data=r.json()
    return {"ok":data.get("username","").lower()=="bytecurioso27" and str(data.get("id",""))==str(config.INSTAGRAM_USER_ID),"id":data.get("id",""),"username":data.get("username",""),"account_type":data.get("account_type","")}

