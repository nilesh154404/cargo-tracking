import re
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

# Default in-memory mappings (fallback when database is offline or not passed)
AIRLINE_PREFIX_MAP: Dict[str, Dict[str, str]] = {
    "160": {
        "carrier_code": "CX",
        "name": "Cathay Pacific Cargo",
        "primary_provider": "cathay_cargo",
        "fallback_providers": "generic_air",
    },
    "176": {
        "carrier_code": "EK",
        "name": "Emirates SkyCargo",
        "primary_provider": "emirates_skycargo",
        "fallback_providers": "generic_air",
    },
    "618": {
        "carrier_code": "SQ",
        "name": "Singapore Airlines Cargo",
        "primary_provider": "singapore_airlines",
        "fallback_providers": "generic_air",
    },
    "020": {
        "carrier_code": "LH",
        "name": "Lufthansa Cargo",
        "primary_provider": "lufthansa_cargo",
        "fallback_providers": "generic_air",
    },
    "131": {
        "carrier_code": "JL",
        "name": "Japan Airlines Cargo",
        "primary_provider": "jal_cargo",
        "fallback_providers": "generic_air",
    },
    "1331": {
        "carrier_code": "JL",
        "name": "Japan Airlines Cargo",
        "primary_provider": "jal_cargo",
        "fallback_providers": "generic_air",
    },
    "016": {
        "carrier_code": "UA",
        "name": "United Cargo",
        "primary_provider": "generic_air",
        "fallback_providers": "",
    },
    "006": {
        "carrier_code": "DL",
        "name": "Delta Cargo",
        "primary_provider": "generic_air",
        "fallback_providers": "",
    },
    "074": {
        "carrier_code": "KL",
        "name": "KLM Cargo",
        "primary_provider": "generic_air",
        "fallback_providers": "",
    },
    "312": {
        "carrier_code": "6E",
        "name": "IndiGo Cargo",
        "primary_provider": "indigo_cargo",
        "fallback_providers": "generic_air",
    },
    "098": {
        "carrier_code": "AI",
        "name": "Air India Cargo",
        "primary_provider": "air_india_cargo",
        "fallback_providers": "generic_air",
    },
    "603": {
        "carrier_code": "UL",
        "name": "SriLankan Cargo",
        "primary_provider": "srilankan_cargo",
        "fallback_providers": "generic_air",
    },
    "141": {
        "carrier_code": "FZ",
        "name": "FlyDubai Cargo",
        "primary_provider": "flydubai_cargo",
        "fallback_providers": "generic_air",
    },
    "235": {
        "carrier_code": "TK",
        "name": "Turkish Cargo",
        "primary_provider": "turkish_cargo",
        "fallback_providers": "generic_air",
    },
    "672": {
        "carrier_code": "BI",
        "name": "Royal Brunei Airlines Cargo",
        "primary_provider": "royal_brunei_cargo",
        "fallback_providers": "generic_air",
    },
    "406": {
        "carrier_code": "5X",
        "name": "UPS Air Cargo",
        "primary_provider": "ups_air_cargo",
        "fallback_providers": "generic_air",
    },
    "198": {
        "carrier_code": "AFCOM",
        "name": "Afcom Cargo",
        "primary_provider": "afcom_cargo",
        "fallback_providers": "generic_air",
    },
    "071": {
        "carrier_code": "ET",
        "name": "Ethiopian Airlines Cargo",
        "primary_provider": "ethiopian_cargo",
        "fallback_providers": "generic_air",
    },
    "217": {
        "carrier_code": "TG",
        "name": "Thai Cargo",
        "primary_provider": "thai_cargo",
        "fallback_providers": "generic_air",
    },
    "157": {
        "carrier_code": "QR",
        "name": "Qatar Airways Cargo",
        "primary_provider": "qatar_cargo",
        "fallback_providers": "generic_air",
    },
    "615": {
        "carrier_code": "DHL",
        "name": "DHL Aviation Cargo",
        "primary_provider": "dhl_aviation_cargo",
        "fallback_providers": "generic_air",
    },
    "936": {
        "carrier_code": "D0",
        "name": "DHL Air",
        "primary_provider": "dhl_aviation_cargo",
        "fallback_providers": "generic_air",
    },
    "607": {
        "carrier_code": "EY",
        "name": "Etihad Cargo",
        "primary_provider": "etihad_cargo",
        "fallback_providers": "generic_air",
    },
    "229": {
        "carrier_code": "KU",
        "name": "Kuwait Airways Cargo",
        "primary_provider": "kuwait_airways",
        "fallback_providers": "generic_air",
    },
    "807": {
        "carrier_code": "AK",
        "name": "AirAsia Cargo",
        "primary_provider": "air_asia",
        "fallback_providers": "generic_air",
    },
    "555": {
        "carrier_code": "SU",
        "name": "Aeroflot Cargo",
        "primary_provider": "aeroflot_cargo",
        "fallback_providers": "generic_air",
    },
    "577": {
        "carrier_code": "AD",
        "name": "Azul Cargo",
        "primary_provider": "azul_cargo",
        "fallback_providers": "generic_air",
    },
    "501": {
        "carrier_code": "7L",
        "name": "Silk Way West Airlines",
        "primary_provider": "silk_way_west_cargo",
        "fallback_providers": "generic_air",
    },
    "125": {
        "carrier_code": "BA",
        "name": "IAG Cargo",
        "primary_provider": "iag_cargo",
        "fallback_providers": "generic_air",
    },
    "072": {
        "carrier_code": "GF",
        "name": "Gulf Air",
        "primary_provider": "champ_cargo",
        "fallback_providers": "generic_air",
    },
}

SEA_CONTAINER_PREFIX_MAP: Dict[str, Dict[str, str]] = {
    "MAEU": {
        "carrier_code": "MSK",
        "name": "Maersk Line",
        "primary_provider": "ldb_container",
        "fallback_providers": "generic_ocean",
    },
    "MRSU": {
        "carrier_code": "MSK",
        "name": "Maersk Line",
        "primary_provider": "ldb_container",
        "fallback_providers": "generic_ocean",
    },
    "MSKU": {
        "carrier_code": "MSK",
        "name": "Maersk Line",
        "primary_provider": "ldb_container",
        "fallback_providers": "generic_ocean",
    },
    "MSCU": {
        "carrier_code": "MSC",
        "name": "Mediterranean Shipping Company",
        "primary_provider": "msc",
        "fallback_providers": "generic_ocean",
    },
    "MSMU": {
        "carrier_code": "MSC",
        "name": "Mediterranean Shipping Company",
        "primary_provider": "msc",
        "fallback_providers": "generic_ocean",
    },
    "MEDU": {
        "carrier_code": "MSC",
        "name": "Mediterranean Shipping Company",
        "primary_provider": "msc",
        "fallback_providers": "generic_ocean",
    },
    "CMAU": {
        "carrier_code": "CMA",
        "name": "CMA CGM",
        "primary_provider": "generic_ocean",
        "fallback_providers": "",
    },
    "HLCU": {
        "carrier_code": "HAP",
        "name": "Hapag-Lloyd",
        "primary_provider": "generic_ocean",
        "fallback_providers": "",
    },
    "ONEU": {
        "carrier_code": "ONE",
        "name": "Ocean Network Express (ONE)",
        "primary_provider": "ldb_container",
        "fallback_providers": "generic_ocean",
    },
    "ONEY": {
        "carrier_code": "ONE",
        "name": "Ocean Network Express (ONE)",
        "primary_provider": "ldb_container",
        "fallback_providers": "generic_ocean",
    },
}


LIVE_SUPPORTED_AIR_PROVIDERS = {"cathay_cargo", "singapore_airlines", "jal_cargo", "indigo_cargo", "air_india_cargo", "srilankan_cargo", "flydubai_cargo", "turkish_cargo", "lufthansa_cargo", "royal_brunei_cargo", "ups_air_cargo", "ethiopian_cargo", "thai_cargo", "qatar_cargo", "dhl_aviation_cargo", "etihad_cargo", "kuwait_airways", "air_asia", "azul_cargo", "aeroflot_cargo", "afcom_cargo", "silk_way_west_cargo", "iag_cargo", "champ_cargo"}
LIVE_SUPPORTED_SEA_PROVIDERS = {"msc", "ldb_container", "one_line"}


class IdentificationResult:
    def __init__(
        self,
        mode: str,
        clean_tracking_number: str,
        carrier_code: str,
        carrier_name: str,
        prefix: str,
        serial_number: str,
        primary_provider: str,
        fallback_providers: list[str],
        is_valid_format: bool = True,
        is_supported: bool = True,
        relatable_message: Optional[str] = None,
    ):
        self.mode = mode
        self.clean_tracking_number = clean_tracking_number
        self.carrier_code = carrier_code
        self.carrier_name = carrier_name
        self.prefix = prefix
        self.serial_number = serial_number
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers
        self.is_valid_format = is_valid_format
        self.is_supported = is_supported
        self.relatable_message = relatable_message

    def to_dict(self):
        return {
            "mode": self.mode,
            "clean_tracking_number": self.clean_tracking_number,
            "carrier_code": self.carrier_code,
            "carrier_name": self.carrier_name,
            "prefix": self.prefix,
            "serial_number": self.serial_number,
            "primary_provider": self.primary_provider,
            "fallback_providers": self.fallback_providers,
            "is_valid_format": self.is_valid_format,
            "is_supported": self.is_supported,
            "relatable_message": self.relatable_message,
        }


def _lookup_db_carrier(db: Optional[Session], prefix: str, mode: str):
    """Query MySQL carriers table for custom carrier provider rules."""
    if not db:
        return None
    try:
        from app.db.models import Carrier
        stmt = select(Carrier).where(
            (Carrier.prefix == prefix)
            | (Carrier.code == prefix)
            | Carrier.prefix.like(f"%{prefix}%"),
            Carrier.mode == mode,
        )
        return db.execute(stmt).scalars().first()
    except Exception:
        return None


def parse_and_identify(
    raw_query: str,
    explicit_mode: Optional[str] = None,
    db: Optional[Session] = None,
) -> IdentificationResult:
    cleaned = raw_query.strip().upper()
    digits_only = re.sub(r"\D", "", cleaned)

    # Normalize 1331 alias to 131 (standard JAL prefix)
    if digits_only.startswith("1331") and len(digits_only) == 12:
        digits_only = "131" + digits_only[4:]
    if cleaned.startswith("1331-"):
        cleaned = "131-" + cleaned[5:]

    # 1. SEA Container detection: Standard ISO 6346 container (4 alpha + 7 digits, e.g. MSMU6484830)
    container_match = re.match(r"^([A-Z]{4})(\d{7})$", cleaned)
    if container_match or (explicit_mode == "SEA" and len(cleaned) >= 7):
        if container_match:
            prefix = container_match.group(1)
            serial = container_match.group(2)
        else:
            prefix = cleaned[:4]
            serial = cleaned[4:]

        # Check DB first
        db_carrier = _lookup_db_carrier(db, prefix, "SEA")
        if db_carrier:
            fallbacks = [
                p.strip()
                for p in (db_carrier.fallback_providers or "").split(",")
                if p.strip()
            ]
            primary_p = db_carrier.primary_provider
            carrier_code = db_carrier.code
            carrier_name = db_carrier.name
        else:
            carrier_info = SEA_CONTAINER_PREFIX_MAP.get(
                prefix,
                {
                    "carrier_code": f"SEA_{prefix}",
                    "name": f"Shipping Line ({prefix})",
                    "primary_provider": "generic_ocean",
                    "fallback_providers": "",
                },
            )
            fallbacks = [
                p.strip()
                for p in carrier_info["fallback_providers"].split(",")
                if p.strip()
            ]
            primary_p = carrier_info["primary_provider"]
            carrier_code = carrier_info["carrier_code"]
            carrier_name = carrier_info["name"]

        is_supported = primary_p in LIVE_SUPPORTED_SEA_PROVIDERS
        relatable_msg = (
            None
            if is_supported
            else f"Shipping line not supported: Container prefix '{prefix}' ({carrier_name}) is currently not supported for live tracking."
        )

        return IdentificationResult(
            mode="SEA",
            clean_tracking_number=f"{prefix}{serial}",
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            prefix=prefix,
            serial_number=serial,
            primary_provider=primary_p,
            fallback_providers=fallbacks,
            is_valid_format=True,
            is_supported=is_supported,
            relatable_message=relatable_msg,
        )

    # 2. AIR Waybill detection: Standard 11-digit AWB (3 prefix + 8 serial)
    if (explicit_mode is None and len(digits_only) == 11) or (explicit_mode == "AIR" and len(digits_only) >= 8):
        prefix = digits_only[:3]
        serial = digits_only[3:]

        # Check DB first
        db_carrier = _lookup_db_carrier(db, prefix, "AIR")
        if db_carrier:
            fallbacks = [
                p.strip()
                for p in (db_carrier.fallback_providers or "").split(",")
                if p.strip()
            ]
            primary_p = db_carrier.primary_provider
            carrier_code = db_carrier.code
            carrier_name = db_carrier.name
        else:
            carrier_info = AIRLINE_PREFIX_MAP.get(
                prefix,
                {
                    "carrier_code": f"AIR_{prefix}",
                    "name": f"Airline Prefix {prefix}",
                    "primary_provider": "generic_air",
                    "fallback_providers": "",
                },
            )
            fallbacks = [
                p.strip()
                for p in carrier_info["fallback_providers"].split(",")
                if p.strip()
            ]
            primary_p = carrier_info["primary_provider"]
            carrier_code = carrier_info["carrier_code"]
            carrier_name = carrier_info["name"]

        is_supported = primary_p in LIVE_SUPPORTED_AIR_PROVIDERS
        relatable_msg = (
            None
            if is_supported
            else f"Airline not supported: Prefix '{prefix}' ({carrier_name}) is currently not supported for live tracking."
        )

        return IdentificationResult(
            mode="AIR",
            clean_tracking_number=f"{prefix}-{serial}",
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            prefix=prefix,
            serial_number=serial,
            primary_provider=primary_p,
            fallback_providers=fallbacks,
            is_valid_format=True,
            is_supported=is_supported,
            relatable_message=relatable_msg,
        )

    # 3. Invalid tracking number format
    detected_mode = "SEA" if re.search(r"[A-Z]{2,}", cleaned) else "AIR"
    return IdentificationResult(
        mode=detected_mode,
        clean_tracking_number=cleaned,
        carrier_code="UNKNOWN",
        carrier_name="Unknown Carrier",
        prefix="",
        serial_number=cleaned,
        primary_provider="none",
        fallback_providers=[],
        is_valid_format=False,
        is_supported=False,
        relatable_message=f"Invalid tracking number format: '{raw_query}'. Expected an 11-digit Air Waybill (e.g. 160-15246221) or standard Sea Container number (e.g. MSMU6484830).",
    )
