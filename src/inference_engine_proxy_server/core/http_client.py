"""
全域 httpx.AsyncClient:
使用 FastAPI 的 lifespan 事件來管理一個全域的 httpx 客戶端實例是標準的最佳實踐。
利用了連線池 (Connection Pooling)，避免了為每個請求重複建立 TCP 連線和 TLS 交握的開銷。
"""

import asyncio
import contextlib
import httpx
from .cache_refresher import refresh_loop

_client: httpx.AsyncClient | None = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        # ✅ 移除 http2=True，讓 httpx 自動協商協定
        _client = httpx.AsyncClient(timeout=5)
    return _client

async def lifespan(app):
    app.state.metrics_task = asyncio.create_task(refresh_loop())

    yield
    if _client is not None:
        await _client.aclose()
    
    app.state.metrics_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await app.state.metrics_task