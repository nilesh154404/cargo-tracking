from app.providers import get_provider
from app.providers.base import ProviderResult


class SeaTrackingTool:
    """Tool used by agents to invoke Ocean Shipping container tracking providers."""

    name = "execute_sea_tracking"
    description = "Executes an Ocean shipping container tracking query using a specific provider (e.g. maersk, generic_ocean)."

    @classmethod
    async def execute(
        cls,
        provider_name: str,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider = get_provider(provider_name)
        if not provider:
            return ProviderResult(
                success=False,
                provider_name=provider_name,
                status_code=404,
                error=f"Sea provider '{provider_name}' not registered in system.",
            )

        return await provider.track(
            prefix=prefix,
            serial=serial,
            tracking_number=tracking_number,
            language=language,
            force_refresh=force_refresh,
        )
