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

    async def _streaming_generator(self, response: httpx.Response) -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        except (httpx.StreamClosed, httpx.ReadError):
            logger.warning("Stream interrupted, likely by client disconnection.")

    async def forward_request(self, req: Request, path: str) -> Response:
        from ..core.constants import BACKEND_TIMEOUT_SECONDS

        url = f"{self.backend_url}/{path}"
        headers = self._filter_headers(dict(req.headers))
        headers.pop("host", None)

        client = get_client()

        # ✅ 讀取完整的請求體，而不是以流式轉發
        request_body = await req.body()

        try:
            async with client.stream(
                method=req.method,
                url=url,
                headers=headers,
                params=req.query_params,
                # ✅ 將完整的請求體傳遞給後端
                content=request_body,
                cookies=req.cookies,
                timeout=BACKEND_TIMEOUT_SECONDS
            ) as r:
                content_type = r.headers.get("content-type", "")

                if "text/event-stream" in content_type.lower():
                    return StreamingResponse(
                        self._streaming_generator(r),
                        status_code=r.status_code,
                        headers=self._filter_headers(dict(r.headers))
                    )
                else:
                    body = await r.aread()
                    return Response(
                        content=body,
                        status_code=r.status_code,
                        headers=self._filter_headers(dict(r.headers))
                    )
        except httpx.ConnectError as e:
            logger.error("Cannot connect to backend service at %s: %s", self.backend_url, e)
            return Response("Backend service is unavailable.", status_code=503)