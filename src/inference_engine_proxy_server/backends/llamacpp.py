import httpx
import time
import logging
from prometheus_client.parser import text_string_to_metric_families
from typing import Tuple, Optional
from .base import BaseBackend
from ..core.constants import MAX_ALLOWED_DEFERRED, MAX_ALLOWED_REQUEST_QUEUE

# Add a logger for this module
logger = logging.getLogger("backend_llamacpp")

class LlamacppBackend(BaseBackend):
    def __init__(self, backend_url) -> None:
        super().__init__(backend_url)
        
    async def fetch_health(self) -> bool:
        """
        Hits /health endpoint to check for basic readiness.
        """
        try:
            from ..core.http_client import get_client
            client = get_client()
            r = await client.get(f"{self.backend_url}/health", timeout=1.0)
            r.raise_for_status() # Raise an exception for 4xx/5xx status codes
            data = r.json()
            # Assuming the health endpoint returns a JSON with a "status" field
            if data.get("status") == "ok":
                return True
        except Exception as e:
            logger.warning("Health check failed for %s: %s", self.backend_url, e)
        return False
    
    async def fetch_metrics(self) -> Tuple[float, bool]:
        """
        Fetches and parses metrics from /metrics endpoint.
        This method no longer handles caching; it just performs the fetch.
        It determines readiness based on metrics and a final health check.
        """
        reqs_processing: Optional[float] = None
        reqs_deferred: Optional[float] = None

        try:
            from ..core.http_client import get_client
            client = get_client()
            r = await client.get(f"{self.backend_url}/metrics", timeout=5.0)
            
            if r.status_code == 200:
                for family in text_string_to_metric_families(r.text):
                    if family.name in ("llamacpp:requests_processing", "llamacpp_requests_processing"):
                        reqs_processing = family.samples[0].value
                    if family.name in ("llamacpp:requests_deferred", "llamacpp_requests_deferred"):
                        reqs_deferred = family.samples[0].value
                    if reqs_processing is not None and reqs_deferred is not None:
                        break
        except Exception as e:
            logger.warning("Metrics fetch failed for %s: %s. Will rely on health check.", self.backend_url, e)

        # Fallback to health check to determine basic readiness
        ready = await self.fetch_health()
        
        # If metrics were successfully fetched, use them to refine readiness
        if reqs_processing is not None and reqs_deferred is not None:
            if reqs_processing >= MAX_ALLOWED_REQUEST_QUEUE:
                ready = False
            if reqs_deferred >= MAX_ALLOWED_DEFERRED:
                ready = False
        
        # If metrics couldn't be fetched, we consider queue length unknown (0 for decision making).
        # If ready is False from health check, queue length doesn't matter.
        final_reqs_processing = reqs_processing if reqs_processing is not None else 0.0

        return final_reqs_processing, ready