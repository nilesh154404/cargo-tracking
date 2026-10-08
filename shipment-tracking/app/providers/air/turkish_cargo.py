"""
Turkish Cargo (TK / prefix 235) provider.

Uses the Turkish Cargo public REST API at www.turkishcargo.com.
No authentication required — just a simple JSON POST to the tracking endpoint.
No Playwright / browser needed.
"""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.turkish_cargo")

# ── API Endpoints ────────────────────────────────────────────────────────
BASE_URL = "https://www.turkishcargo.com"
TRACKING_URL = f"{BASE_URL}/api/proxy/onlineServices/shipmentTracking"

API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "EN",
    "content-type": "application/json",
    "origin": BASE_URL,
    "referer": f"{BASE_URL}/en/cargo-tracking",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# ── Status Mapping ───────────────────────────────────────────────────────
_STATUS_MAP: Dict[str, str] = {
    "BKD": "BKD",
    "RCS": "RCS",
    "DEP": "DEP",
    "RCF": "RCF",
    "NFD": "NFD",
    "DLV": "DLV",
    "ARR": "ARR",
    "AWD": "AWD",
    "MAN": "MAN",
    "PRE": "PRE",
    "TRM": "TRM",
    "CCD": "CCD",
    "AWR": "AWR",
    "FOH": "FOH",
}

_STATUS_MESSAGE_MAP: Dict[str, str] = {
    "BKD": "Booked",
    "RCS": "Shipment accepted at origin",
    "DEP": "Departed",
    "RCF": "Received from flight",
    "NFD": "Notified for delivery",
    "DLV": "Delivered to consignee",
    "ARR": "Arrived at station",
    "AWD": "Awaiting customs clearance",
    "MAN": "Manifested on flight",
    "PRE": "Prepared for loading",
    "TRM": "Transferred to another carrier",
    "CCD": "Customs cleared",
    "AWR": "Documents received",
    "FOH": "Freight on hand",
}

# Overall status from the API's actualStatus field
_OVERALL_STATUS_MAP: Dict[str, str] = {
    "Delivered": "Delivered",
    "In Transit": "In Transit",
    "Booked": "Booked",
    "Accepted": "Accepted",
    "Departed": "In Transit",
    "Arrived": "In Transit",
    "Notified for Delivery": "Out for Delivery",
}


class TurkishCargoProvider(BaseProvider):
    """
    Live provider for Turkish Cargo (TK / prefix 235).
    Uses the Turkish Cargo public shipment tracking REST API.

    Authentication flow (none required):
        1. GET the tracking page to establish Akamai session cookie.
        2. POST /api/proxy/onlineServices/shipmentTracking with AWB details.
        No OAuth, no JWT, no Playwright.
    """

    name = "turkish_cargo"
    mode = "AIR"

    # ── Main Track Method ─────────────────────────────────────────────

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=20.0, verify=True
            ) as client:

                # ── Step 1: GET tracking page for Akamai session cookie ──
                await client.get(
                    f"{BASE_URL}/en/cargo-tracking",
                    headers={
                        "user-agent": API_HEADERS["user-agent"],
                        "accept": "text/html",
                    },
                )

                # ── Step 2: POST tracking request ────────────────────────
                logger.info(f"TurkishCargo: Tracking AWB {prefix}-{serial}...")
                payload = {
                    "trackingFilters": [
                        {
                            "shipmentPrefix": prefix,
                            "masterDocumentNumber": serial,
                        }
                    ]
                }

                resp = await client.post(
                    TRACKING_URL, json=payload, headers=API_HEADERS
                )
                resp.raise_for_status()
                data = resp.json()

                latency = round((time.time() - start_time) * 1000, 2)

                # ── Step 3: Parse the response ───────────────────────────
                api_status = data.get("status")
                if api_status != "SUCCESS":
                    error_msg = data.get("message", "Unknown error from Turkish Cargo API.")
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=resp.status_code,
                        error=f"Turkish Cargo API error: {error_msg}",
                        latency_ms=latency,
                    )

                return self._parse_tracking_response(
                    data=data, prefix=prefix, serial=serial, latency=latency
                )

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Turkish Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"TurkishCargo HTTP error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code,
                error=str(exc),
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"TurkishCargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    # ── Response Parsing ─────────────────────────────────────────────

    def _parse_tracking_response(
        self,
        data: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the Turkish Cargo shipmentTracking API response."""
        try:
            trackings = (data.get("result") or {}).get("shipmentTrackings", [])
            if not trackings:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=(
                        f"No shipment records found for {prefix}-{serial} "
                        f"on Turkish Cargo. Please verify the tracking number."
                    ),
                    latency_ms=latency,
                )

            shipment = trackings[0]

            # ── Extract basic shipment info ───────────────────────────
            origin = shipment.get("originCode")
            destination = shipment.get("destinationCode")
            pieces = shipment.get("pieces")
            weight_val = shipment.get("weight")
            weight_unit = "kg" if (shipment.get("weightUnit") or "KG").upper() == "KG" else "lb"
            volume = shipment.get("volume")

            # ── Parse tracking events ─────────────────────────────────
            # Use trackingHistoryDetails for full event history
            history_events = shipment.get("trackingHistoryDetails") or []
            events = self._build_events(history_events)

            # ── Determine overall status ──────────────────────────────
            actual_status = shipment.get("actualStatus", "Unknown")
            status = _OVERALL_STATUS_MAP.get(actual_status, actual_status)

            # ── Build flight legs from bookingFlightDetails ───────────
            booking_flights = shipment.get("bookingFlightDetails") or []
            flight_legs = self._build_flight_legs(booking_flights)

            # ── Latest event ──────────────────────────────────────────
            latest_event = None
            if events:
                last = events[-1]
                latest_event = {
                    "station": last.get("station"),
                    "status_code": last.get("status_code"),
                    "status_message": last.get("status_message"),
                    "event_time": last.get("event_time"),
                    "flight_info": last.get("flight_info"),
                    "pieces": last.get("pieces"),
                    "weight": last.get("weight"),
                    "raw_status": None,
                }

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=status,
                message=f"Shipment tracked successfully via Turkish Cargo.",
                origin=origin,
                destination=destination,
                pieces=pieces,
                weight={"value": weight_val, "unit": weight_unit} if weight_val else None,
                volume=volume,
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "Turkish Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin_name": shipment.get("origin"),
                    "destination_name": shipment.get("destination"),
                    "product": shipment.get("product"),
                    "latest_acceptance_time": shipment.get("latestAcceptanceTime"),
                    "actual_status_station": shipment.get("actualStatusStation"),
                    "flight_legs": flight_legs,
                },
            )

        except Exception as exc:
            logger.error(f"TurkishCargo: Failed to parse response: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse Turkish Cargo response: {exc}",
                latency_ms=latency,
            )

    # ── Event Builders ────────────────────────────────────────────────

    def _build_events(self, history_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build normalized events from trackingHistoryDetails."""
        events = []
        for item in history_details:
            raw_status = item.get("status", "")
            status_code = _STATUS_MAP.get(raw_status, raw_status)
            description = item.get("description") or _STATUS_MESSAGE_MAP.get(raw_status, raw_status)

            # Parse datetime: "07-Sep-2026 11:28:02" or "07-Sep-2026 17:11:40.095"
            event_time = self._parse_tk_datetime(item.get("actualDatetime"))

            # Build flight info string if available
            flight_no = item.get("flightNo")
            station = item.get("station")
            flight_info = None
            if flight_no:
                flight_info = flight_no

            events.append({
                "station": station,
                "status_code": status_code,
                "status_message": description,
                "event_time": event_time,
                "flight_info": flight_info,
                "pieces": item.get("actualPieces") or item.get("plannedPieces"),
                "weight": item.get("actualWeight") or item.get("plannedWeight"),
                "raw_status": raw_status,
            })

        # Sort events by event_time
        events.sort(key=lambda e: e.get("event_time") or "")
        return events

    def _build_flight_legs(self, booking_flights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build flight leg details from bookingFlightDetails."""
        legs = []
        for i, flight in enumerate(booking_flights):
            legs.append({
                "leg_number": i + 1,
                "carrier": flight.get("carrierCode"),
                "flight_number": f"{flight.get('carrierCode', '')}{flight.get('flightNumber', '')}",
                "origin": flight.get("originCode"),
                "destination": flight.get("destinationCode"),
                "etd": flight.get("etd"),
                "eta": flight.get("eta"),
                "flight_date": flight.get("flightDate"),
                "pieces": flight.get("pieces"),
                "weight": flight.get("weight"),
                "volume": flight.get("volume"),
                "booking_status": flight.get("flightBookingStatus"),
            })
        return legs

    @staticmethod
    def _parse_tk_datetime(dt_str: Optional[str]) -> Optional[str]:
        """
        Parse Turkish Cargo datetime strings like:
            '07-Sep-2026 11:28:02'
            '07-Sep-2026 17:11:40.095'
        Returns ISO 8601 format: '2026-09-07T11:28:02'
        """
        if not dt_str:
            return None
        try:
            # Strip milliseconds if present
            clean = dt_str.split(".")[0].strip()
            dt = datetime.strptime(clean, "%d-%b-%Y %H:%M:%S")
            return dt.isoformat()
        except (ValueError, AttributeError):
            return dt_str
