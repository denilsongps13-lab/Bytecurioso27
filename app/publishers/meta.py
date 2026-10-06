import requests
from app import config

def _endpoint(path):
    return f"https://graph.instagram.com/{path.lstrip('/')}"

def post_instagram_image(image_url, caption):
    if not (config.META_ENABLED and config.META_ACCESS_TOKEN and config.INSTAGRAM_USER_ID):
        return {"status":"skipped","reason":"Instagram não configurado"}
    create=requests.post(_endpoint(f"{config.INSTAGRAM_USER_ID}/media"),data={
        "image_url":image_url,
        "caption":caption,
        "access_token":config.META_ACCESS_TOKEN
    },timeout=60)
    create.raise_for_status()
    cid=create.json()["id"]
    publish=requests.post(_endpoint(f"{config.INSTAGRAM_USER_ID}/media_publish"),data={
        "creation_id":cid,
        "access_token":config.META_ACCESS_TOKEN
    },timeout=60)
    publish.raise_for_status()
    return {"status":"published","id":publish.json().get("id","")}
