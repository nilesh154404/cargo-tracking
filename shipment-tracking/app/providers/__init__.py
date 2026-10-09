from typing import Dict, Optional
from app.providers.base import BaseProvider
from app.providers.air.cathay_cargo import CathayCargoProvider
from app.providers.air.emirates_skycargo import EmiratesSkyCargoProvider
from app.providers.air.singapore_airlines import SingaporeAirlinesCargoProvider
from app.providers.air.lufthansa_cargo import LufthansaCargoProvider
from app.providers.air.jal_cargo import JalCargoProvider
from app.providers.air.indigo_cargo import IndigoCargoProvider
from app.providers.air.air_india_cargo import AirIndiaCargoProvider
from app.providers.air.srilankan_cargo import SriLankanCargoProvider
from app.providers.air.flydubai_cargo import FlyDubaiCargoProvider
from app.providers.air.turkish_cargo import TurkishCargoProvider
from app.providers.air.royal_brunei_cargo import RoyalBruneiCargoProvider
from app.providers.air.ups_air_cargo import UpsAirCargoProvider
from app.providers.air.ethiopian_cargo import EthiopianCargoProvider
from app.providers.air.thai_cargo import ThaiCargoProvider
from app.providers.air.qatar_cargo import QatarCargoProvider
from app.providers.air.dhl_aviation_cargo import DHLAviationCargoProvider
from app.providers.air.etihad_cargo import EtihadCargoProvider
from app.providers.air.kuwait_airways import KuwaitAirwaysProvider
from app.providers.air.air_asia import AirAsiaProvider
from app.providers.air.azul_cargo import AzulCargoProvider
from app.providers.air.aeroflot_cargo import AeroflotCargoProvider
from app.providers.air.afcom_cargo import AfcomCargoProvider
from app.providers.air.generic_air import GenericAirProvider
from app.providers.air.silk_way_west_cargo import SilkWayWestCargoProvider
from app.providers.air.iag_cargo import IagCargoProvider
from app.providers.air.champ_cargo import ChampCargoProvider
from app.providers.air.maskargo import MasKargoProvider
from app.providers.air.virgin_atlantic_cargo import VirginAtlanticCargoProvider
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
    "indigo_cargo": IndigoCargoProvider(),
    "air_india_cargo": AirIndiaCargoProvider(),
    "srilankan_cargo": SriLankanCargoProvider(),
    "flydubai_cargo": FlyDubaiCargoProvider(),
    "turkish_cargo": TurkishCargoProvider(),
    "royal_brunei_cargo": RoyalBruneiCargoProvider(),
    "ups_air_cargo": UpsAirCargoProvider(),
    "ethiopian_cargo": EthiopianCargoProvider(),
    "thai_cargo": ThaiCargoProvider(),
    "qatar_cargo": QatarCargoProvider(),
    "dhl_aviation_cargo": DHLAviationCargoProvider(),
    "etihad_cargo": EtihadCargoProvider(),
    "kuwait_airways": KuwaitAirwaysProvider(),
    "air_asia": AirAsiaProvider(),
    "azul_cargo": AzulCargoProvider(),
    "aeroflot_cargo": AeroflotCargoProvider(),
    "afcom_cargo": AfcomCargoProvider(),
    "silk_way_west_cargo": SilkWayWestCargoProvider(),
    "iag_cargo": IagCargoProvider(),
    "champ_cargo": ChampCargoProvider(),
    "maskargo": MasKargoProvider(),
    "virgin_atlantic_cargo": VirginAtlanticCargoProvider(),
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
