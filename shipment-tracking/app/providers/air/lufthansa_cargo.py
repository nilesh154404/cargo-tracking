"""
Lufthansa Cargo (LH / prefix 020) provider.

Uses the public REST API at api-external.lufthansa-cargo.com.
No authentication required — direct CORS GET with lufthansa-cargo.com origin.
No Playwright / browser needed.

Single-step flow:
    GET /stp/shipments-details/{prefix}{serial}
    Returns full event history, flight info, milestone plan, booking details.
"""

import time
import logging
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.lufthansa_cargo")

# ── API Configuration ────────────────────────────────────────────────────
API_BASE = "https://api-external.lufthansa-cargo.com/stp/shipments-details"

LH_HEADERS = {
    "accept": "application/json",
    "origin": "https://www.lufthansa-cargo.com",
    "referer": "https://www.lufthansa-cargo.com/",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# ── Status Mapping ───────────────────────────────────────────────────────
IATA_STATUS_MAP = {
    "BKD": "Booked",
    "RCS": "Shipment Received",
    "FOH": "Freight on Hand",
    "MAN": "Manifested",
    "DEP": "Departed",
    "ARR": "Arrived",
    "RCF": "Received from Flight",
    "NFD": "Ready for Pick-up",
    "DLV": "Delivered",
    "DIS": "Discrepancy",
    "TFD": "Transferred",
    "RCT": "Received from Another Airline",
}

STATUS_CLASSIFICATION = {
    "DLV": "Delivered",
    "NFD": "Arrived",
    "ARR": "Arrived",
    "RCF": "Arrived",
    "DEP": "In Transit",
    "MAN": "In Transit",
    "TFD": "In Transit",
    "RCT": "In Transit",
    "RCS": "Accepted",
    "FOH": "Freight on Hand",
    "BKD": "Booked",
    "DIS": "Exception",
}


class LufthansaCargoProvider(BaseProvider):
    """
    Live provider for Lufthansa Cargo (LH / prefix 020).
    Uses Lufthansa Cargo's public shipment tracking REST API.

    Authentication flow (none required):
        GET /stp/shipments-details/{awb_number}
        No OAuth, no JWT, no cookies, no Playwright.
    """

    name = "lufthansa_cargo"
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

        if prefix != "020":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Lufthansa Cargo (expects 020)",
                latency_ms=latency,
            )

        # AWB path: concatenate prefix + serial (no dash)
        awb_path = f"{prefix}{serial}"
        url = f"{API_BASE}/{awb_path}"

        try:
            async with httpx.AsyncClient(
                timeout=20.0, verify=True, follow_redirects=True
            ) as client:
                logger.info(f"LH Cargo: Fetching {url}")
                resp = await client.get(url, headers=LH_HEADERS)

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"Lufthansa Cargo API HTTP {resp.status_code}: {resp.text[:200]}",
                    latency_ms=latency,
                )

            data = resp.json()
            return self._parse_response(data, prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Lufthansa Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to Lufthansa Cargo API: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"LH Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error tracking Lufthansa Cargo shipment: {exc}",
                latency_ms=latency,
            )

    # ── Response Parsing ──────────────────────────────────────────────

    def _parse_response(
        self,
        data: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the Lufthansa Cargo shipments-details response."""
        try:
            # Check availability
            availability = data.get("availabilityDetails", {})
            if not availability.get("isAvailable", False):
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"AWB {prefix}-{serial} not found or requires login on Lufthansa Cargo.",
                    latency_ms=latency,
                )

            awb_details = data.get("awbDetails", {})
            origin_airport = awb_details.get("originAirport", {})
            dest_airport = awb_details.get("destinationAirport", {})
            origin = origin_airport.get("airportCode")
            destination = dest_airport.get("airportCode")
            latest_event_code = awb_details.get("latestEvent", "")

            # Pieces & weight
            pieces_info = awb_details.get("piecesInformation", {})
            pieces = pieces_info.get("piecesCount")
            weight_val = pieces_info.get("piecesWeight")
            weight_unit_raw = pieces_info.get("piecesWeightUnit", "")
            weight_unit = self._normalize_weight_unit(weight_unit_raw)

            # Volume
            volume_val = pieces_info.get("piecesVolume")
            volume_unit_raw = pieces_info.get("piecesVolumeUnit", "")

            # Product
            product = awb_details.get("product", {})
            product_name = product.get("productName")
            product_code = product.get("productCode")
            special_cargo_codes = product.get("specialCargoCodes", [])

            # ── Build events from statusHistories ─────────────────────
            status_histories = data.get("statusHistories", [])
            events = self._build_events(status_histories)

            # ── Overall status ────────────────────────────────────────
            status = STATUS_CLASSIFICATION.get(latest_event_code, "In Transit")

            # ── Build flight legs ─────────────────────────────────────
            flight_info_list = data.get("flightInformation", [])
            flight_legs = self._build_flight_legs(flight_info_list)

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

            # ── LAT / TOA ─────────────────────────────────────────────
            lat = awb_details.get("latestAcceptanceTime")
            toa_planned = awb_details.get("plannedTimeOfAvailability")
            toa_actual = awb_details.get("actualTimeOfAvailability")

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=status,
                origin=origin,
                destination=destination,
                pieces=pieces,
                weight={"value": weight_val, "unit": weight_unit} if weight_val else None,
                volume=volume_val if volume_val else None,
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "Lufthansa Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin_name": origin_airport.get("airportName"),
                    "destination_name": dest_airport.get("airportName"),
                    "product": product_name,
                    "product_code": product_code,
                    "special_cargo_codes": special_cargo_codes,
                    "volume_unit": self._normalize_volume_unit(volume_unit_raw),
                    "lat": lat,
                    "toa_planned": toa_planned,
                    "toa_actual": toa_actual,
                    "flight_legs": flight_legs,
                },
            )

        except Exception as exc:
            logger.error(f"LH Cargo: Failed to parse response: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse Lufthansa Cargo response: {exc}",
                latency_ms=latency,
            )

    # ── Event Builders ────────────────────────────────────────────────

    def _build_events(self, status_histories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build normalized events from statusHistories array."""
        events = []
        for entry in status_histories:
            event_type = entry.get("cargoEventType", "")
            actual = entry.get("actualCargoEvent", {})
            station = entry.get("stationAirport", {})
            flight = entry.get("flight")
            planned = entry.get("planedCargoEvent", {})

            # Description
            disc_code = actual.get("discrepancyCode")
            if event_type == "DIS" and disc_code:
                description = f"Discrepancy - {disc_code}"
            else:
                description = IATA_STATUS_MAP.get(event_type, event_type)

            # Flight info
            flight_info = None
            if flight:
                fd = flight.get("flightDesignator", {})
                carrier = fd.get("carrierCode", "")
                flt_num = fd.get("flightNumber", "")
                flight_info = f"{carrier}{flt_num}".strip() or None

            # Pieces & weight from actual event
            actual_pieces_info = actual.get("pieceInformation", {})
            evt_pieces = actual_pieces_info.get("piecesCount")
            evt_weight = actual_pieces_info.get("piecesWeight")

            # Planned time
            planned_time = planned.get("eventDateTime") if planned else None

            events.append({
                "station": station.get("airportCode"),
                "station_name": station.get("airportName"),
                "status_code": event_type,
                "status_message": description,
                "event_time": actual.get("eventDateTime"),
                "planned_time": planned_time,
                "flight_info": flight_info,
                "pieces": evt_pieces,
                "weight": evt_weight,
                "raw_status": event_type,
            })

        # Sort by event_time
        events.sort(key=lambda e: e.get("event_time") or "")
        return events

    def _build_flight_legs(self, flight_info_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build flight leg details from flightInformation array."""
        legs = []
        for i, flight in enumerate(flight_info_list):
            origin = flight.get("originAirport", {})
            dest = flight.get("destinationAirport", {})
            legs.append({
                "leg_number": i + 1,
                "flight_number": flight.get("flightNumber"),
                "board_point": origin.get("airportCode"),
                "board_point_name": origin.get("airportName"),
                "off_point": dest.get("airportCode"),
                "off_point_name": dest.get("airportName"),
                "flight_date": flight.get("flightDate"),
                "aircraft_type": flight.get("aircraftType"),
                "scheduled_departure": flight.get("scheduledDepartureTime"),
                "scheduled_arrival": flight.get("scheduledArrivalTime"),
                "actual_departure": flight.get("actualDepartureTime"),
                "actual_arrival": flight.get("actualArrivalTime"),
                "estimated_departure": flight.get("estimatedDepartureTime"),
                "estimated_arrival": flight.get("estimatedArrivalTime"),
            })
        return legs

    # ── Utility Methods ───────────────────────────────────────────────

    @staticmethod
    def _normalize_weight_unit(raw: str) -> str:
        """Normalize weight unit string from API."""
        if not raw or raw == "UNKNOWN":
            return "kg"
        mapping = {"KILOGRAM": "kg", "POUNDS": "lb", "KG": "kg", "LB": "lb"}
        return mapping.get(raw.upper(), "kg")

    @staticmethod
    def _normalize_volume_unit(raw: str) -> str:
        """Normalize volume unit string from API."""
        if not raw or raw == "UNKNOWN":
            return "cbm"
        mapping = {"CUBIC_METRES": "cbm", "CUBIC_FEET": "cft", "CBM": "cbm", "CFT": "cft"}
        return mapping.get(raw.upper(), "cbm")
