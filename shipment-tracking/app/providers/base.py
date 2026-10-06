from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ProviderResult(BaseModel):
    success: bool
    provider_name: str
    status_code: Optional[int] = None
    status: str = "UNKNOWN"
    origin: Optional[str] = None
    destination: Optional[str] = None
    pieces: Optional[int] = None
    weight: Optional[Dict[str, Any]] = None
    volume: Optional[float] = None
    events: List[Dict[str, Any]] = []
    latest_event: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class BaseProvider(ABC):
    name: str = "base_provider"
    mode: str = "AIR"

    @abstractmethod
    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        pass
