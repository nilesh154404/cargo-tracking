from typing import Dict, Optional
from app.providers.base import BaseProvider
from app.providers.air.cathay_cargo import CathayCargoProvider
from app.providers.air.emirates_skycargo import EmiratesSkyCargoProvider
from app.providers.air.singapore_airlines import SingaporeAirlinesCargoProvider
from app.providers.air.lufthansa_cargo import LufthansaCargoProvider
from app.providers.air.jal_cargo import JalCargoProvider
from app.providers.air.generic_air import GenericAirProvider
from app.providers.sea.maersk import MaerskProvider
from app.providers.sea.msc import MscProvider
from app.providers.sea.ldb_container import LdbContainerProvider
from app.providers.sea.generic_ocean import GenericOceanProvider

_ldb_instance = LdbContainerProvider()

_REGISTRY: Dict[str, BaseProvider] = {
    "cathay_cargo": CathayCargoProvider(),
    "emirates_skycargo": EmiratesSkyCargoProvider(),
    "singapore_airlines": SingaporeAirlinesCargoProvider(),
    "lufthansa_cargo": LufthansaCargoProvider(),
    "jal_cargo": JalCargoProvider(),
    "generic_air": GenericAirProvider(),
    "maersk": MaerskProvider(),
    "msc": MscProvider(),
    "ldb_container": _ldb_instance,
    "one_line": _ldb_instance,
    "generic_ocean": GenericOceanProvider(),
}


def register_provider(name: str, provider: BaseProvider):
    """Dynamically register a new provider adapter."""
    _REGISTRY[name] = provider


def get_provider(name: str) -> Optional[BaseProvider]:
    return _REGISTRY.get(name)


def list_providers() -> Dict[str, BaseProvider]:
    return dict(_REGISTRY)
