import inspect
from typing import Optional
from app.providers import get_provider
from app.providers.base import ProviderResult


class AirTrackingTool:
    """Tool used by agents to invoke Air Cargo providers with retries and fallbacks."""

    name = "execute_air_tracking"
    description = "Executes an Air tracking query using a specific provider (e.g. cathay_cargo, emirates_skycargo, generic_air)."

    @classmethod
    async def execute(
        cls,
        provider_name: str,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
        **kwargs,
    ) -> ProviderResult:
        provider = get_provider(provider_name)
        if not provider:
            return ProviderResult(
                success=False,
                provider_name=provider_name,
                status_code=404,
                error=f"Provider '{provider_name}' not registered in system.",
            )

        sig = inspect.signature(provider.track)
        has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        call_kwargs = kwargs if has_var_keyword else {k: v for k, v in kwargs.items() if k in sig.parameters}

        return await provider.track(
            prefix=prefix,
            serial=serial,
            tracking_number=tracking_number,
            language=language,
            force_refresh=force_refresh,
            **call_kwargs,
        )
