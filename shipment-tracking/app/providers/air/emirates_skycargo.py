import time
from typing import Optional
from app.providers.base import BaseProvider, ProviderResult


class EmiratesSkyCargoProvider(BaseProvider):
    name = "emirates_skycargo"
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
            status_code=501,
            status="AIRLINE_NOT_SUPPORTED",
            error=f"Airline not supported: Emirates SkyCargo ({prefix}) live tracking is not yet integrated.",
            events=[],
            latest_event=None,
            raw_data={"carrier": "Emirates SkyCargo", "awb": f"{prefix}-{serial}"},
            latency_ms=latency,
        )
