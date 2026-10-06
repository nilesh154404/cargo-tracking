import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

CCN_TRACK_URL = (
    "https://cube.ccnexchange.com/quick-service/618f5141-5855-4f64-b29c-992dc23daa2f/PP/1/TrackSearch_Status"
)

CCN_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-IN,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://www.siacargo.com",
    "referer": "https://www.siacargo.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

IATA_STATUS_MAP = {
    "BKD": "Booked",
    "RCS": "Accepted / Received",
    "FOH": "Freight on Hand",
    "FWB": "Electronic AWB Received",
    "MAN": "Manifested",
    "DEP": "Departed",
    "ARR": "Arrived",
    "RCF": "Received from Flight",
    "NFD": "Consignee Notified of Arrival",
    "AWD": "Documents Delivered",
    "DLV": "Delivered",
    "DIS": "Discrepancy",
    "TFD": "Transferred",
}

STATUS_CLASSIFICATION = {
    "DLV": "Delivered",
    "NFD": "Arrived",
    "ARR": "Arrived",
    "RCF": "Arrived",
    "DEP": "In Transit",
    "MAN": "In Transit",
    "TFD": "In Transit",
    "RCS": "Accepted",
    "FOH": "Freight on Hand",
    "BKD": "Booked",
    "FWB": "Booked",
}


class SingaporeAirlinesCargoProvider(BaseProvider):
    name = "singapore_airlines"
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

        if prefix != "618":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Singapore Airlines Cargo (expects 618)",
                latency_ms=latency,
            )

        # Standard SIA / CCN exchange expects format: "618-XXXXXXX"
        awb_formatted = f"{prefix}-{serial}"
        payload = {
            "awbNumber": [awb_formatted],
            "airline": "SQ",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    CCN_TRACK_URL,
                    headers=CCN_HEADERS,
                    json=payload,
                )

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"CCNExchange API HTTP {resp.status_code}: {resp.text[:200]}",
                    latency_ms=latency,
                )

            data = resp.json()
            shipment_list = data.get("shipmentStatus") or []

            if not shipment_list:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"No shipment records found for AWB {awb_formatted}",
                    latency_ms=latency,
                    raw_data=data,
                )

            shipment = shipment_list[0]
            origin = shipment.get("origin") or None
            destination = shipment.get("destination") or None
            last_status = (shipment.get("lastStatus") or "").strip().upper()
            flight_number = shipment.get("flightNumber") or None
            flight_date_raw = shipment.get("flightDateDate") or None
            last_updated_raw = shipment.get("lastUpdatedDate") or None

            # If origin, destination, and flightNumber are all blank, AWB is empty/invalid
            if not origin and not destination and not flight_number and not last_status:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"AWB {awb_formatted} not active or no route details available",
                    latency_ms=latency,
                    raw_data=data,
                )

            # Build standardized events
            events: List[Dict[str, Any]] = []

            # 1. Flight movement event if available
            if flight_date_raw and not flight_date_raw.startswith("0001-01-01"):
                is_departed = last_status in ["DEP", "ARR", "RCF", "NFD", "DLV"]
                dep_code = "DEP" if is_departed else "BKD"
                events.append({
                    "station": origin or "SIN",
                    "status_code": dep_code,
                    "status_message": (
                        f"Flight {flight_number} Departed"
                        if is_departed
                        else f"Flight {flight_number} Scheduled"
                    ),
                    "event_time": flight_date_raw,
                    "flight_info": flight_number,
                })

            # 2. Last milestone event
            status_desc = IATA_STATUS_MAP.get(last_status, f"Status: {last_status}")
            event_station = destination if last_status in ["ARR", "RCF", "NFD", "DLV"] else (origin or "SIN")
            event_time = (
                last_updated_raw
                if last_updated_raw and not last_updated_raw.startswith("0001-01-01")
                else (flight_date_raw if flight_date_raw and not flight_date_raw.startswith("0001-01-01") else datetime.now(timezone.utc).isoformat())
            )

            events.append({
                "station": event_station,
                "status_code": last_status or "INFO",
                "status_message": f"{status_desc} (Flight {flight_number})" if flight_number else status_desc,
                "event_time": event_time,
                "flight_info": flight_number,
            })

            normalized_status = STATUS_CLASSIFICATION.get(last_status, last_status or "In Transit")

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=normalized_status,
                origin=origin,
                destination=destination,
                events=events,
                latest_event=events[-1] if events else None,
                raw_data=data,
                latency_ms=latency,
            )

        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to CCNExchange: {str(exc)}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error parsing CCNExchange response: {str(exc)}",
                latency_ms=latency,
            )
