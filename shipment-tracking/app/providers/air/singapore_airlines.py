"""
Singapore Airlines Cargo (SQ / prefix 618) provider.

Uses the CCN Exchange (Cube) public REST API at cube.ccnexchange.com.
No authentication required — direct CORS POST with siacargo.com origin.
No Playwright / browser needed.

Two-step flow:
    1. POST TrackSearch_Status  → quick summary (origin, dest, last status)
    2. POST TrackSearch_Details → full event history, booking info, flight legs
"""

import time
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.singapore_airlines")

# ── CCN Cube API Endpoints ───────────────────────────────────────────────
CUBE_BASE = "https://cube.ccnexchange.com/quick-service/618f5141-5855-4f64-b29c-992dc23daa2f/PP/1"
STATUS_URL = f"{CUBE_BASE}/TrackSearch_Status"
DETAILS_URL = f"{CUBE_BASE}/TrackSearch_Details"

CCN_HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "origin": "https://www.siacargo.com",
    "referer": "https://www.siacargo.com/",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
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
    "FWB": "Electronic AWB Received",
    "MAN": "Manifested",
    "DEP": "Departed",
    "ARR": "Arrived",
    "RCF": "Received from Flight",
    "NFD": "Ready for Pick-up",
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
    """
    Live provider for Singapore Airlines Cargo (SQ / prefix 618).
    Uses the CCN Exchange (Cube) public tracking REST API.

    Authentication flow (none required):
        1. POST TrackSearch_Status  → quick status check
        2. POST TrackSearch_Details → full event history + booking info
        No OAuth, no JWT, no cookies, no Playwright.
    """

    name = "singapore_airlines"
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

        if prefix != "618":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Singapore Airlines Cargo (expects 618)",
                latency_ms=latency,
            )

        awb_formatted = f"{prefix}-{serial}"

        try:
            async with httpx.AsyncClient(
                timeout=20.0, verify=True, follow_redirects=True
            ) as client:

                # ── Step 1: Quick status check ────────────────────────
                status_payload = {"awbNumber": [awb_formatted], "airline": "SQ"}
                logger.info(f"SIACargo: Checking status for AWB {awb_formatted}...")
                resp1 = await client.post(
                    STATUS_URL, json=status_payload, headers=CCN_HEADERS
                )

                if resp1.status_code != 200:
                    latency = round((time.time() - start_time) * 1000, 2)
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=resp1.status_code,
                        error=f"CCN Exchange API HTTP {resp1.status_code}: {resp1.text[:200]}",
                        latency_ms=latency,
                    )

                status_data = resp1.json()
                shipment_list = status_data.get("shipmentStatus") or []

                if not shipment_list:
                    latency = round((time.time() - start_time) * 1000, 2)
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error=(
                            f"No shipment records found for {awb_formatted} "
                            f"on Singapore Airlines Cargo. Please verify the tracking number."
                        ),
                        latency_ms=latency,
                    )

                summary = shipment_list[0]

                # Check if AWB actually has data
                origin = summary.get("origin") or None
                destination = summary.get("destination") or None
                last_status_code = (summary.get("lastStatus") or "").strip().upper()
                if not origin and not destination and not last_status_code:
                    latency = round((time.time() - start_time) * 1000, 2)
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        error=f"AWB {awb_formatted} not active or no route details available",
                        latency_ms=latency,
                    )

                # ── Step 2: Get full details ──────────────────────────
                logger.info(f"SIACargo: Fetching details for AWB {awb_formatted}...")
                details_payload = {
                    "awbPrefix": prefix,
                    "awbSuffix": serial,
                    "type": "public",
                }
                resp2 = await client.post(
                    DETAILS_URL, json=details_payload, headers=CCN_HEADERS
                )

                latency = round((time.time() - start_time) * 1000, 2)

                if resp2.status_code != 200:
                    # Fall back to status-only data
                    logger.warning(
                        f"SIACargo: Details API returned {resp2.status_code}, "
                        f"using status-only data."
                    )
                    return self._parse_status_only(
                        summary=summary, prefix=prefix, serial=serial, latency=latency
                    )

                details = resp2.json()
                return self._parse_details_response(
                    details=details,
                    summary=summary,
                    prefix=prefix,
                    serial=serial,
                    latency=latency,
                )

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Singapore Airlines Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to CCN Exchange: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"SIACargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error tracking SIA Cargo shipment: {exc}",
                latency_ms=latency,
            )

    # ── Full Details Parsing ──────────────────────────────────────────

    def _parse_details_response(
        self,
        details: Dict[str, Any],
        summary: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the TrackSearch_Details response for full event history."""
        try:
            origin = details.get("origin") or summary.get("origin")
            destination = details.get("destination") or summary.get("destination")

            # ── Parse weight (format: "610K" -> 610 kg) ──────────────
            weight_raw = details.get("weight") or ""
            weight_val, weight_unit = self._parse_weight(weight_raw)
            pieces = self._safe_int(details.get("pieces"))

            # ── Build events from shipmentHistory ─────────────────────
            history = details.get("shipmentHistory") or []
            events = self._build_events(history)

            # ── Determine overall status ──────────────────────────────
            last_status = details.get("lastShipmentStatus") or {}
            last_code = last_status.get("code", "").strip().upper()
            if not last_code and events:
                last_code = events[-1].get("status_code", "")
            status = STATUS_CLASSIFICATION.get(last_code, "In Transit")

            # ── Build flight legs from bookingInformation ─────────────
            booking_info = details.get("bookingInformation") or []
            flight_legs = self._build_flight_legs(booking_info)

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
                message="Shipment tracked successfully via Singapore Airlines Cargo.",
                origin=origin,
                destination=destination,
                pieces=pieces,
                weight={"value": weight_val, "unit": weight_unit} if weight_val else None,
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "Singapore Airlines Cargo",
                    "awb": f"{prefix}-{serial}",
                    "shc": summary.get("shc"),
                    "last_status_description": details.get("status"),
                    "flight_legs": flight_legs,
                },
            )

        except Exception as exc:
            logger.error(f"SIACargo: Failed to parse details response: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse SIA Cargo response: {exc}",
                latency_ms=latency,
            )

    # ── Status-Only Fallback ──────────────────────────────────────────

    def _parse_status_only(
        self,
        summary: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Fallback parser using only the TrackSearch_Status summary."""
        origin = summary.get("origin")
        destination = summary.get("destination")
        last_status = (summary.get("lastStatus") or "").strip().upper()
        flight_number = summary.get("flightNumber")
        last_updated_raw = summary.get("lastUpdatedDate")

        status_desc = IATA_STATUS_MAP.get(last_status, f"Status: {last_status}")
        normalized_status = STATUS_CLASSIFICATION.get(last_status, "In Transit")

        event_station = (
            destination if last_status in ["ARR", "RCF", "NFD", "DLV"] else (origin or "SIN")
        )

        events = [{
            "station": event_station,
            "status_code": last_status or "INFO",
            "status_message": f"{status_desc} ({flight_number})" if flight_number else status_desc,
            "event_time": last_updated_raw,
            "flight_info": flight_number.strip() if flight_number else None,
            "pieces": None,
            "weight": None,
            "raw_status": last_status,
        }]

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=normalized_status,
            message="Shipment tracked via Singapore Airlines Cargo (summary only).",
            origin=origin,
            destination=destination,
            latest_event=events[-1] if events else None,
            events=events,
            latency_ms=latency,
            raw_data=summary,
        )

    # ── Event Builders ────────────────────────────────────────────────

    def _build_events(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build normalized events from shipmentHistory."""
        events = []
        for item in history:
            raw_code = (item.get("code") or "").strip().upper()
            description = item.get("statusShipment") or IATA_STATUS_MAP.get(raw_code, raw_code)

            # Parse ISO datetime from shipmentDate
            event_time = item.get("shipmentDate")

            # Flight info
            flight_details = item.get("flightDetails")
            flight_info = flight_details.strip() if flight_details and flight_details != "NA" else None

            # Parse weight
            weight_raw = item.get("weight") or ""
            weight_val, _ = self._parse_weight(weight_raw)

            events.append({
                "station": item.get("station"),
                "status_code": raw_code,
                "status_message": description,
                "event_time": event_time,
                "flight_info": flight_info,
                "pieces": self._safe_int(item.get("pieces")),
                "weight": weight_val,
                "raw_status": raw_code,
            })

        # Sort by event_time
        events.sort(key=lambda e: e.get("event_time") or "")
        return events

    def _build_flight_legs(self, booking_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build flight leg details from bookingInformation."""
        legs = []
        for i, flight in enumerate(booking_info):
            legs.append({
                "leg_number": i + 1,
                "flight_number": (flight.get("flightNumber") or "").strip(),
                "board_point": flight.get("boardPoint"),
                "off_point": flight.get("offPoint"),
                "board_date": flight.get("boardDate"),
                "off_date": flight.get("offDate"),
                "board_datetime": flight.get("boardDateDate"),
                "off_datetime": flight.get("offDateDate"),
                "aircraft_type": flight.get("aircraftType"),
                "pieces": self._safe_int(flight.get("pieces")),
                "weight": flight.get("weight"),
                "booking_status": flight.get("bookingStatus"),
                "partial": flight.get("partialIndicator") or None,
            })
        return legs

    # ── Utility Methods ───────────────────────────────────────────────

    @staticmethod
    def _parse_weight(weight_str: str):
        """Parse weight string like '610K' -> (610.0, 'kg')."""
        if not weight_str:
            return None, "kg"
        match = re.match(r"^([\d.]+)\s*([KL]?)$", weight_str.strip(), re.IGNORECASE)
        if match:
            val = float(match.group(1))
            unit = "lb" if match.group(2).upper() == "L" else "kg"
            return val, unit
        try:
            return float(weight_str), "kg"
        except (ValueError, TypeError):
            return None, "kg"

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        """Safely convert a value to int."""
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
