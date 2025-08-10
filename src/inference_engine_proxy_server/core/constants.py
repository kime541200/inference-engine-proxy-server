import sys
import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm-proxy")

BACKENDS = [b.strip() for b in os.getenv("BACKENDS", "").split(",") if b.strip()]
if not BACKENDS:
    logger.error("No BACKENDS defined in .env")
    sys.exit(1)


EXCLUDE_HEADERS = {
    "content-encoding", "connection",
    "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "upgrade", "proxy-connection", "content-length"
}


# --- OPTIMIZED CACHE STRUCTURE ---
# cache: {backend_url: {"dynamic": {...}, "static": {...}}}
# "dynamic" part is updated frequently by the refresh loop(src/inference_engine_proxy_server/core/cache_refresher.py).
# "static" part is fetched once and then reused(provider & model name).
_METRICS_CACHE: Dict[str, Dict[str, Any]] = {}
METRICS_CACHE_TTL_SECONDS = float(os.getenv("METRICS_CACHE_TTL_SECONDS", "3"))   # 秒

BACKEND_TIMEOUT_SECONDS = int(os.getenv("BACKEND_TIMEOUT_SECONDS", "300"))

MAX_ALLOWED_REQUEST_QUEUE=int(os.getenv("MAX_ALLOWED_REQUEST_QUEUE", "4"))
MAX_ALLOWED_DEFERRED=int(os.getenv("MAX_ALLOWED_DEFERRED", "2"))