import os
from dotenv import load_dotenv
load_dotenv()

def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1","true","yes","on"}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","")
TELEGRAM_OWNER_CHAT_ID = os.getenv("TELEGRAM_OWNER_CHAT_ID","")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
OPENAI_MODEL = os.getenv("OPENAI_MODEL","gpt-6-luna")
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES","5"))
AUTO_PUBLISH_LOW_RISK = env_bool("AUTO_PUBLISH_LOW_RISK", False)
MAX_POSTS_PER_CYCLE = int(os.getenv("MAX_POSTS_PER_CYCLE","3"))
MAX_ARTICLE_AGE_HOURS = int(os.getenv("MAX_ARTICLE_AGE_HOURS","48"))
META_ENABLED = env_bool("META_ENABLED", False)
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION","v24.0")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN","")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID","")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID","")
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN","")
TIKTOK_ENABLED = env_bool("TIKTOK_ENABLED", False)
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN","")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL","https://bytecurioso27-news.onrender.com").rstrip("/")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","")
GEMINI_MODEL = os.getenv("GEMINI_MODEL","gemini-2.5-flash-lite")


VISUAL_AUDIT_PREVIEWS = env_bool("VISUAL_AUDIT_PREVIEWS", False)
