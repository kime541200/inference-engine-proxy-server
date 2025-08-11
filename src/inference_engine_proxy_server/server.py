import logging
import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# -------------------- 基本設定 --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxy-server")


# -------------------- 工具函式 --------------------
from .core.constants import BACKENDS
from .core.functions import choose_backend, get_all_metrics_from_cache
from .core.http_client import lifespan


# -------------------- FastAPI --------------------

app = FastAPI(lifespan=lifespan)

# CORS 中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Provides a health check of the proxy and its backends based on cached data."""
    # This is now a fast, non-blocking cache read.
    backend_statuses = get_all_metrics_from_cache()
    
    ready_backends = [status['backend'] for status in backend_statuses if status['ready']]
    
    proxy_status = "ok" if ready_backends else "degraded"
    
    return {
        "status": proxy_status,
        "available_backends": ready_backends,
        "total_backends": len(BACKENDS),
        "timestamp": time.time(),
        "details": backend_statuses
    }


@app.get("/")
async def read_root():
    return {"message": "Welcome to vLLM/llama.cpp inference engine proxy server!"}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy(full_path: str, request: Request):
    backend = await choose_backend()
    if not backend:
        return Response("No backend available", status_code=503)
    return await backend.forward_request(request, full_path)