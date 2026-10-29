import time
from typing import Optional
from app.providers.base import BaseProvider, ProviderResult
from app.providers.sea.containertracking_net import ContainerTrackingNetProvider


class GenericOceanProvider(BaseProvider):
    """
    Generic Ocean Container Provider.
    Delegates to ContainerTrackingNetProvider (https://containertracking.net/)
    to provide universal global coverage across 310+ shipping lines and leasing companies.
    """
    name = "generic_ocean"
    mode = "SEA"

    def __init__(self):
        self._containertracking = ContainerTrackingNetProvider()

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
        **kwargs,
    ) -> ProviderResult:
        result = await self._containertracking.track(
            prefix=prefix,
            serial=serial,
            tracking_number=tracking_number,
            language=language,
            force_refresh=force_refresh,
            **kwargs,
        )
        # Attribute provider name to generic_ocean for execution trail clarity
        result.provider_name = self.name
        return result
