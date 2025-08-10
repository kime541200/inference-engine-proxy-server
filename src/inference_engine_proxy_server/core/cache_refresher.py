import asyncio
import time
import logging
from typing import Tuple, Optional
from .constants import BACKENDS, METRICS_CACHE_TTL_SECONDS, _METRICS_CACHE
from ..utils.utils import a_get_model_name, a_check_provider

logger = logging.getLogger("cache-refresher")


# ✅ 將 fetch_metrics 函式移動到這裡，並重新命名為 _fetch_backend_metrics
async def _fetch_backend_metrics(backend_url: str, provider: str) -> Optional[Tuple[float, bool]]:
    """
    Fetches dynamic metrics for a given backend based on its provider.
    """
    from ..backends.llamacpp import LlamacppBackend
    from ..backends.vllm import VllmBackend

    backend = None
    if provider == "llamacpp":
        backend = LlamacppBackend(backend_url)
    elif provider == "vllm":
        backend = VllmBackend(backend_url)
    else:
        return None
    return await backend.fetch_metrics()


async def refresh_loop():
    """
    Periodically refreshes the metrics and status of all backends.
    It also fetches static information (provider, model_name) once per backend.
    """
    while True:
        start_time = time.time()
        
        # --- Stage 1: Ensure static info is cached for all backends ---
        for backend_url in BACKENDS:
            # If backend is new or static info fetching failed before
            if backend_url not in _METRICS_CACHE or not _METRICS_CACHE[backend_url].get("static", {}).get("provider"):
                if backend_url not in _METRICS_CACHE:
                    # Initialize cache structure for new backend
                    _METRICS_CACHE[backend_url] = {"dynamic": {}, "static": {}}
                try:
                    logger.info("Fetching static info for %s...", backend_url)
                    model_name = await a_get_model_name(backend_url)
                    provider = await a_check_provider(backend_url, model_name)
                    _METRICS_CACHE[backend_url]["static"] = {
                        "provider": provider,
                        "model_name": model_name
                    }
                    logger.info("Successfully fetched static info for %s: provider=%s", backend_url, provider)
                except Exception as e:
                    logger.error("Failed to fetch static info for %s: %s. Will retry in the next cycle.", backend_url, e)
        
        # --- Stage 2: Fetch dynamic metrics for ready backends ---
        tasks = []
        for backend_url, cache_entry in _METRICS_CACHE.items():
            provider = cache_entry.get("static", {}).get("provider")
            if provider: # Only fetch metrics if we know the provider
                # ✅ 使用在此檔案中定義的函式
                tasks.append(_fetch_backend_metrics(backend_url, provider))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # --- Stage 3: Update cache with new dynamic metrics ---
        now = time.time()
        backend_index = 0
        for backend_url, cache_entry in _METRICS_CACHE.items():
            if not cache_entry.get("static", {}).get("provider"):
                continue # Skip backends we couldn't get static info for

            res = results[backend_index]
            backend_index += 1
            
            if isinstance(res, Exception):
                logger.warning("Metrics error for %s -> %s", backend_url, res)
                # Mark backend as not ready if metrics fetch fails
                _METRICS_CACHE[backend_url]["dynamic"] = {
                    "timestamp": now,
                    "requests_processing": float("inf"),
                    "ready": False
                }
                continue

            # res = (requests_processing, ready)
            requests_processing, ready = res
            _METRICS_CACHE[backend_url]["dynamic"] = {
                "timestamp": now,
                "requests_processing": requests_processing,
                "ready": ready
            }

        # Sleep until the next cycle
        elapsed_time = time.time() - start_time
        await asyncio.sleep(max(0, METRICS_CACHE_TTL_SECONDS - elapsed_time))