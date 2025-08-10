from abc import ABC, abstractmethod
import logging
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from typing import Tuple, AsyncGenerator
import httpx

from ..core.constants import EXCLUDE_HEADERS
from ..core.http_client import get_client

logger = logging.getLogger(__name__)

class BaseBackend(ABC):
    def __init__(self, backend_url) -> None:
        super().__init__()
        self.backend_url = backend_url
    
    @abstractmethod
    async def fetch_health(self) -> bool:
        pass
    
    @abstractmethod
    async def fetch_metrics(self) -> Tuple[float, bool]:
        pass
    
    def _filter_headers(self, headers: dict):
        return {k: v for k, v in headers.items() if k.lower() not in EXCLUDE_HEADERS}

    async def forward_request(self, req: Request, path: str) -> Response:
        """
        實現非同步請求轉發，並能智慧判斷使用流式或非流式回應。
        此版本修正了非同步上下文管理器的生命週期問題。
        """
        from ..core.constants import BACKEND_TIMEOUT_SECONDS

        url = f"{self.backend_url}/{path}"
        headers = self._filter_headers(dict(req.headers))
        headers.pop("host", None)
        request_body = await req.body()
        client = get_client()

        # 步驟 1: 手動建立請求並發送，但不使用 `async with`
        try:
            req_for_httpx = client.build_request(
                method=req.method,
                url=url,
                headers=headers,
                params=req.query_params,
                content=request_body,
                timeout=BACKEND_TIMEOUT_SECONDS,
            )
            response = await client.send(req_for_httpx, stream=True)
        except httpx.ConnectError as e:
            logger.error("Cannot connect to backend service at %s: %s", self.backend_url, e)
            return Response("Backend service is unavailable.", status_code=503)

        # 步驟 2: 檢查回應類型
        content_type = response.headers.get("content-type", "")

        # 對於非流式回應，讀取完畢後手動關閉連線
        if "text/event-stream" not in content_type.lower():
            try:
                body = await response.aread()
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=self._filter_headers(dict(response.headers)),
                )
            finally:
                await response.aclose()
        
        # 步驟 3: 對於流式回應，建立一個生成器來管理連線生命週期
        async def streaming_generator(res: httpx.Response):
            try:
                async for chunk in res.aiter_bytes():
                    yield chunk
            except (httpx.StreamClosed, httpx.ReadError):
                logger.warning("Stream interrupted, likely by client disconnection.")
            finally:
                # 確保在生成器結束時（無論正常或異常），連線都被關閉
                await res.aclose()
                logger.info("Backend response stream closed.")

        return StreamingResponse(
            streaming_generator(response),
            status_code=response.status_code,
            headers=self._filter_headers(dict(response.headers)),
        )