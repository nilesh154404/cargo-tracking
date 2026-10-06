import time
from typing import Optional
from app.providers.base import BaseProvider, ProviderResult


class GenericAirProvider(BaseProvider):
    name = "generic_air"
    mode = "AIR"

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        latency = round((time.time() - start_time) * 1000 + 10, 2)

        return ProviderResult(
            success=False,
            provider_name=self.name,
            status_code=404,
            status="AIRLINE_NOT_SUPPORTED",
            error=f"Airline not supported: Prefix '{prefix}' is not currently integrated for live tracking.",
            events=[],
            latest_event=None,
            raw_data={
                "source": "Air Cargo Gateway",
                "awb": f"{prefix}-{serial}",
            },
            latency_ms=latency,
        )
