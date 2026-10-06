import time
from typing import Optional
from app.providers.base import BaseProvider, ProviderResult


class MaerskProvider(BaseProvider):
    name = "maersk"
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
        container_id = f"{prefix}{serial}".upper()

        return ProviderResult(
            success=False,
            provider_name=self.name,
            status_code=501,
            status="SHIPPING_LINE_NOT_SUPPORTED",
            error=f"Shipping line not supported: Maersk Line ({prefix}) live tracking is not yet integrated.",
            events=[],
            latest_event=None,
            raw_data={"carrier": "Maersk Line", "container": container_id},
            latency_ms=latency,
        )
