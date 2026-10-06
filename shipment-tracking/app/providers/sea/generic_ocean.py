import time
from typing import Optional
from app.providers.base import BaseProvider, ProviderResult


class GenericOceanProvider(BaseProvider):
    name = "generic_ocean"
    mode = "SEA"

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
            status="SHIPPING_LINE_NOT_SUPPORTED",
            error=f"Shipping line not supported: Container prefix '{prefix}' is not currently integrated for live tracking.",
            events=[],
            latest_event=None,
            raw_data={"source": "Ocean Container Gateway", "tracking_number": tracking_number},
            latency_ms=latency,
        )
