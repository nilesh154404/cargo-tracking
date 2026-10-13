from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import json as _json


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
    request_curl: Optional[str] = None
    response_body: Optional[str] = None
    latency_ms: float = 0.0


class BaseProvider(ABC):
    name: str = "base_provider"
    mode: str = "AIR"

    @staticmethod
    def build_curl_command(
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """Build a cURL command string from the HTTP request components."""
        parts = [f"curl -X {method.upper()}"]
        parts.append(f" '{url}'")

        if headers:
            for key, value in headers.items():
                # Mask Authorization tokens for security
                if key.lower() in ("authorization",) and "bearer" in value.lower():
                    display_val = "Bearer ***REDACTED***"
                else:
                    display_val = value
                parts.append(f" -H '{key}: {display_val}'")

        if body is not None:
            if isinstance(body, (dict, list)):
                body_str = _json.dumps(body, default=str)
                parts.append(f" -d '{body_str}'")
            elif isinstance(body, str):
                parts.append(f" -d '{body}'")

        return " \\\n".join(parts)

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

