import logging
import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html

# -------------------- 基本設定 --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm-proxy")


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
# 掛載靜態文件
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy(full_path: str, request: Request):
    backend = await choose_backend()
    if not backend:
        return Response("No backend available", status_code=503)
    return await backend.forward_request(request, full_path)


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


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url=f"/static/swagger-ui-bundle.js",
        swagger_css_url=f"/static/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )


@app.get("/")
async def read_root():
    return {"message": "Welcome to vLLM/llama.cpp inference engine proxy server!"}