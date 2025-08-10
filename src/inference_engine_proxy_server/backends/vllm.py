import httpx
import time
from prometheus_client.parser import text_string_to_metric_families
from typing import Tuple
from .base import BaseBackend

class VllmBackend(BaseBackend):
    def __init__(self, backend_url) -> None:
        super().__init__(backend_url)
        
    
    async def fetch_health(self) -> bool:
        # TODO
        pass
    
    
    async def fetch_metrics(self) -> Tuple[float, bool]:
        # TODO
        pass