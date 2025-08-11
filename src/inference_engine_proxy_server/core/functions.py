import random
import time
from typing import Union, Optional, List, Dict, Any

from ..core.constants import BACKENDS, _METRICS_CACHE, METRICS_CACHE_TTL_SECONDS
from ..backends.llamacpp import LlamacppBackend
from ..backends.vllm import VllmBackend

def get_all_metrics_from_cache() -> List[Dict[str, Any]]:
    """
    Gets the current status of all backends directly from the cache.
    This is a fast, non-blocking operation.
    """
    results = []
    for backend_url in BACKENDS:
        cache_entry = _METRICS_CACHE.get(backend_url, {})
        dynamic_info = cache_entry.get("dynamic", {"ready": False})
        results.append({
            "backend": backend_url,
            "ready": dynamic_info.get("ready", False),
            "metrics": dynamic_info
        })
    return results

async def choose_backend() -> Optional[Union[LlamacppBackend, VllmBackend]]:
    """
    Chooses the best backend based on metrics from the cache.
    This function no longer performs any network I/O and is extremely fast.
    """
    now = time.time()
    candidates = []
    
    for backend_url, cache_entry in _METRICS_CACHE.items():
        dynamic_info = cache_entry.get("dynamic", {})
        ts = dynamic_info.get("timestamp", 0)
        ready = dynamic_info.get("ready", False)
        reqs = dynamic_info.get("requests_processing", float("inf"))

        # Check if backend is ready and its data is not too stale (with a grace period)
        if ready and (now - ts) < METRICS_CACHE_TTL_SECONDS * 2:
            candidates.append((backend_url, reqs))

    if not candidates:
        return None

    # Find the minimum load value among candidates
    min_load = min(reqs for _, reqs in candidates)
    
    # Get all backends that have the same minimum load
    best_options = [url for url, reqs in candidates if reqs == min_load]
    
    # Randomly select one from the best options to distribute load evenly
    selected_backend_url = random.choice(best_options)
    
    # --- NO MORE AWAITS! ---
    # Get the provider directly from the cache
    provider = _METRICS_CACHE[selected_backend_url].get("static", {}).get("provider")

    if provider == "llamacpp":
        return LlamacppBackend(selected_backend_url)
    elif provider == "vllm":
        return VllmBackend(selected_backend_url)
    else:
        # This should not happen if the cache is working correctly
        return None