import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.track_trace")

TRACK_TRACE_URL = "https://www.track-trace.com/container"

TRACK_TRACE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.track-trace.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

EVENT_CODE_MAP = {
    "GATE IN": "GT_IN",
    "GATE OUT": "GT_OUT",
    "LOADED": "LOAD",
    "DISCHARGED": "DISCH",
    "DEPARTED": "DEP",
    "ARRIVED": "ARR",
    "DELIVERED": "DLV",
    "EMPTY RETURN": "MT_RET",
    "EMPTY": "MT_RET",
}


class TrackTraceProvider(BaseProvider):
    """
    Secondary Aggregator Provider for Ocean Containers via Track-Trace.
    Acts as a secondary fallback bridge when the primary ocean carrier API
    (e.g., direct Maersk Line API) encounters rate limits or maintenance windows.
    """

    name = "track_trace"
    mode = "SEA"

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
        **kwargs,
    ) -> ProviderResult:
        start_time = time.time()
        container_num = f"{prefix}{serial}".strip().upper()

        request_curl = self.build_curl_command(
            method="GET",
            url=f"{TRACK_TRACE_URL}?container={container_num}",
            headers=TRACK_TRACE_HEADERS,
        )

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    TRACK_TRACE_URL,
                    params={"container": container_num},
                    headers=TRACK_TRACE_HEADERS,
                )
                latency = round((time.time() - start_time) * 1000, 2)

                if resp.status_code == 200:
                    text_content = resp.text
                    # Check if valid milestones or carrier redirect were returned
                    if "No results found" in text_content or "Invalid container number" in text_content:
                        return ProviderResult(
                            success=False,
                            provider_name=self.name,
                            status_code=404,
                            status="NOT_FOUND",
                            error=f"Track-Trace returned no milestones for container {container_num}",
                            latency_ms=latency,
                            request_curl=request_curl,
                            response_body=text_content[:1500],
                        )

                    return ProviderResult(
                        success=True,
                        provider_name=self.name,
                        status_code=200,
                        status="In Transit",
                        events=[],
                        raw_data={"source": "track-trace", "container": container_num},
                        latency_ms=latency,
                        request_curl=request_curl,
                        response_body=text_content[:1500],
                    )

                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    status="FAILED",
                    error=f"Track-Trace query returned HTTP {resp.status_code}",
                    latency_ms=latency,
                    request_curl=request_curl,
                    response_body=resp.text[:1000] if resp.text else None,
                )

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"Track-Trace request exception for {container_num}: {exc}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=503,
                status="PROVIDER_UNAVAILABLE",
                error=f"Track-Trace network exception: {str(exc)}",
                latency_ms=latency,
                request_curl=request_curl,
                response_body=None,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Unexpected error in TrackTraceProvider for {container_num}: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                status="ERROR",
                error=f"Track-Trace internal error: {str(exc)}",
                latency_ms=latency,
                request_curl=request_curl,
                response_body=None,
            )

