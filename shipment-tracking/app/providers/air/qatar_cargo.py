"""
Qatar Airways Cargo (QR / prefix 157) provider.

Uses the Salesforce Aura/Lightning API at qrcargo.com.
No authentication required — public Apex action endpoint.
No Playwright / browser needed.

Single-step flow:
    POST /s/sfsites/aura?r=18&aura.ApexAction.execute=1
    with Salesforce Aura message containing AWB prefix + number.
    Returns structured JSON with flights + movement events.
"""

import json
import re
import time
import logging
import datetime
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.qatar_cargo")

# ── API Configuration ────────────────────────────────────────────────────
AURA_URL = "https://www.qrcargo.com/s/sfsites/aura?r=18&aura.ApexAction.execute=1"

QR_HEADERS = {
    "accept": "*/*",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://www.qrcargo.com",
    "referer": "https://www.qrcargo.com/s/track-your-shipment",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# Salesforce Aura context (public community app — no auth token needed)
AURA_CONTEXT = {
    "mode": "PROD",
    "fwuid": "WUdfaXlIZDNDQ0lZLWNFZDMtVGZ3d2tVMjdnTGFERUU2S3FfSVdrcU92bkExNC4xOTIuODM4ODYwOA",
    "app": "siteforce:communityApp",
    "loaded": {
        "APPLICATION@markup://siteforce:communityApp": "1712_xZHiuQoc1HHcvGz4vs6mGA"
    },
    "dn": [],
    "globals": {},
    "uad": True,
}

# ── Status Mapping ───────────────────────────────────────────────────────
STATUS_MAP = {
    "RCS": "Accepted",
    "BKD": "Booked",
    "MAN": "In Transit",
    "DEP": "In Transit",
    "ARR": "Arrived",
    "RCF": "Arrived",
    "NFD": "Arrived",
    "DLV": "Delivered",
    "AWD": "Arrived",
    "CRC": "Cleared",
    "TFD": "In Transit",
}


class QatarCargoProvider(BaseProvider):
    """
    Live provider for Qatar Airways Cargo (QR / prefix 157).
    Uses the Salesforce Aura/Lightning API (public Apex action).

    Authentication flow (none required):
        POST /s/sfsites/aura with Apex action QCG_CTRL_TrackShipment.QCG_getAwbDetailsMS
        No OAuth, no JWT, no cookies, no Playwright.
        aura.token = null (public guest access).
    """

    name = "qatar_cargo"
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

        if prefix != "157":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Qatar Cargo (expects 157)",
                latency_ms=latency,
            )

        # Build Salesforce Aura message
        message = {
            "actions": [{
                "id": "120;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "",
                    "classname": "QCG_CTRL_TrackShipment",
                    "method": "QCG_getAwbDetailsMS",
                    "params": {
                        "awbs": [{
                            "documentType": "MAWB",
                            "documentPrefix": prefix,
                            "documentNumber": serial,
                        }]
                    },
                    "cacheable": False,
                    "isContinuation": False,
                }
            }]
        }

        form_data = {
            "message": json.dumps(message),
            "aura.context": json.dumps(AURA_CONTEXT),
            "aura.pageURI": "/s/track-your-shipment",
            "aura.token": "null",
        }

        try:
            async with httpx.AsyncClient(
                timeout=20.0, verify=True, follow_redirects=True
            ) as client:
                logger.info(f"Qatar Cargo: POST Aura API for {prefix}-{serial}")
                resp = await client.post(AURA_URL, data=form_data, headers=QR_HEADERS)

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"Qatar Cargo Aura API HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            return self._parse_response(resp.json(), prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Qatar Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to Qatar Cargo: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Qatar Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error tracking Qatar Cargo shipment: {exc}",
                latency_ms=latency,
            )

    # ── Response Parser ───────────────────────────────────────────────

    def _parse_response(
        self,
        data: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the Salesforce Aura JSON response."""
        try:
            actions = data.get("actions", [])
            if not actions or actions[0].get("state") != "SUCCESS":
                error_msg = "Qatar Cargo Aura API returned non-SUCCESS state"
                if actions and actions[0].get("error"):
                    error_msg = str(actions[0]["error"])
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=error_msg,
                    latency_ms=latency,
                )

            rv = actions[0]["returnValue"]["returnValue"]
            tracking_list = rv.get("cargoTrackingSOs", [])

            if not tracking_list:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"AWB {prefix}-{serial} not found on Qatar Cargo.",
                    latency_ms=latency,
                )

            tracking = tracking_list[0]

            # ── Summary ───────────────────────────────────────────────
            origin = tracking.get("origin")
            destination = tracking.get("destination")
            pieces_str = tracking.get("pieces", "0")
            weight_str = tracking.get("weight", "0")
            volume_str = tracking.get("volume")
            volume_unit = tracking.get("volumeUnit", "")
            shipment_status = tracking.get("shipmentUpdate", "")

            pieces = int(pieces_str) if pieces_str else None
            weight_val = float(weight_str) if weight_str else None
            volume_val = float(volume_str) if volume_str else None

            # ── Flight Legs ───────────────────────────────────────────
            flight_legs = []
            for fl in tracking.get("cargoTrackingFlightList", []):
                flight_legs.append({
                    "flight_number": fl.get("flightNumber", "").strip(),
                    "departure_station": fl.get("segmentOfDeparture"),
                    "arrival_station": fl.get("segmetnOfArrival"),  # Note: typo in API
                    "departure_time": fl.get("departedDateTime"),
                    "arrival_time": fl.get("arrivalDate"),
                    "status": fl.get("flightStatus"),
                    "operation_type": fl.get("operationType"),
                    "pieces": fl.get("pieces"),
                    "weight": fl.get("weight"),
                    "volume": fl.get("volume"),
                })

            # ── Events ────────────────────────────────────────────────
            events = []
            for evt in tracking.get("cargoTrackingMvtStausList", []):
                status_code = evt.get("movementStatus", "UNK")
                event_time = self._parse_qr_datetime(
                    evt.get("eventDate", ""), evt.get("eventTime", "")
                )

                evt_pieces = None
                try:
                    evt_pieces = int(evt.get("shipmentPieces", ""))
                except (ValueError, TypeError):
                    pass

                evt_weight = None
                try:
                    evt_weight = float(evt.get("shipmentWeight", ""))
                except (ValueError, TypeError):
                    pass

                events.append({
                    "station": evt.get("eventAirport"),
                    "station_name": None,
                    "status_code": status_code,
                    "status_message": evt.get("movementDetails", ""),
                    "event_time": event_time,
                    "flight_info": self._extract_flight(evt.get("movementDetails", "")),
                    "pieces": evt_pieces,
                    "weight": evt_weight,
                    "raw_status": status_code,
                })

            # Events come newest-first, reverse to chronological
            events.reverse()

            # ── Overall Status ────────────────────────────────────────
            overall_status = "Booked"
            if events:
                last_code = events[-1].get("status_code", "")
                overall_status = STATUS_MAP.get(last_code, shipment_status or "In Transit")

            # ── Latest Event ──────────────────────────────────────────
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
                status=overall_status,
                origin=origin,
                destination=destination,
                pieces=pieces,
                weight={"value": weight_val, "unit": "kg"} if weight_val else None,
                volume=volume_val,
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "Qatar Airways Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin": origin,
                    "destination": destination,
                    "shipment_info": tracking.get("shipmentInfo"),
                    "snr_number": tracking.get("snrNumber"),
                    "flight_legs": flight_legs,
                },
            )

        except Exception as exc:
            logger.error(f"Qatar Cargo: Failed to parse response: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse Qatar Cargo response: {exc}",
                latency_ms=latency,
            )

    # ── Utilities ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_qr_datetime(date_str: str, time_str: str) -> Optional[str]:
        """Parse QR date/time: 'Thu, 10 Sep 2026' + '04:21' -> ISO string."""
        if not date_str:
            return None
        try:
            month_map = {
                "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
                "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
                "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
            }
            # Remove day name: "Thu, 10 Sep 2026" -> "10 Sep 2026"
            cleaned = re.sub(r'^[A-Za-z]+,\s*', '', date_str.strip())
            parts = cleaned.split()
            if len(parts) >= 3:
                day = int(parts[0])
                month = month_map.get(parts[1], 1)
                year = int(parts[2])
                hour, minute = 0, 0
                if time_str:
                    # Remove (+1) suffixes
                    time_clean = re.sub(r'\(\+\d+\)', '', time_str).strip()
                    if ":" in time_clean:
                        tp = time_clean.split(":")
                        hour = int(tp[0])
                        minute = int(tp[1])
                dt = datetime.datetime(year, month, day, hour, minute)
                return dt.isoformat()
        except Exception:
            pass
        return f"{date_str} {time_str}"

    @staticmethod
    def _extract_flight(details: str) -> Optional[str]:
        """Extract flight number from movement details like 'Departed from DOH on QR0500/11-Sep-2026'."""
        match = re.search(r'QR\s*[\-]?\s*(\d{4})', details)
        if match:
            return f"QR{match.group(1)}"
        return None
