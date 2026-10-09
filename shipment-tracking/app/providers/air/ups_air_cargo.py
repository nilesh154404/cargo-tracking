"""
UPS Air Cargo (5X / prefix 406) provider.

Uses the public tracking page at aircargo.ups.com.
No authentication required — simple GET request returns server-rendered HTML
with all tracking data embedded in tables.
No Playwright / browser needed.

Single-step flow:
    GET /en-US/Tracking?awbPrefix={prefix}&awbNumber={serial}
    Returns HTML page with Summary header + TrackDataTable.
"""

import re
import time
import logging
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.ups_air_cargo")

# ── API Configuration ────────────────────────────────────────────────────
TRACKING_URL = "https://www.aircargo.ups.com/en-US/Tracking"

UPS_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# ── Status Mapping ───────────────────────────────────────────────────────
STATUS_MAP = {
    "booked": "Booked",
    "booked *": "Booked",
    "received": "Accepted",
    "departed": "In Transit",
    "arrived": "Arrived",
    "delivered": "Delivered",
    "notified": "Arrived",
    "transferred": "In Transit",
}


# ── HTML Table Parser ────────────────────────────────────────────────────
class _TableParser(HTMLParser):
    """Lightweight parser to extract <table> data from UPS Air Cargo HTML."""

    def __init__(self):
        super().__init__()
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self.tables: List[Dict[str, Any]] = []
        self._cur_table: List[List[str]] = []
        self._cur_row: List[str] = []
        self._cur_cell = ""
        self._table_id = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "table":
            self._in_table = True
            self._table_id = attrs_dict.get("id", "")
            self._cur_table = []
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._cur_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._cur_cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._cur_row.append(self._cur_cell.strip())
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._cur_row:
                self._cur_table.append(self._cur_row)
        elif tag == "table" and self._in_table:
            self._in_table = False
            if self._cur_table:
                self.tables.append({"id": self._table_id, "rows": self._cur_table})

    def handle_data(self, data):
        if self._in_cell:
            self._cur_cell += data


class UpsAirCargoProvider(BaseProvider):
    """
    Live provider for UPS Air Cargo (5X / prefix 406).
    Uses the public aircargo.ups.com tracking page via GET request.

    Authentication flow (none required):
        GET /en-US/Tracking?awbPrefix=406&awbNumber=<serial>
        No OAuth, no JWT, no cookies, no Playwright.
    """

    name = "ups_air_cargo"
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

        if prefix != "406":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by UPS Air Cargo (expects 406)",
                latency_ms=latency,
            )

        params = {
            "awbPrefix": prefix,
            "awbNumber": serial,
        }

        try:
            async with httpx.AsyncClient(
                timeout=20.0, verify=True, follow_redirects=True
            ) as client:
                logger.info(f"UPS Air Cargo: GET {TRACKING_URL} for {prefix}-{serial}")
                resp = await client.get(TRACKING_URL, params=params, headers=UPS_HEADERS)

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"UPS Air Cargo HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            return self._parse_html(resp.text, prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="UPS Air Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to UPS Air Cargo: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"UPS Air Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error tracking UPS Air Cargo shipment: {exc}",
                latency_ms=latency,
            )

    # ── HTML Parsing ──────────────────────────────────────────────────

    def _parse_html(
        self,
        html: str,
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the UPS Air Cargo tracking page HTML."""
        try:
            # Check if tracking data is present
            if "TrackDataTable" not in html:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"AWB {prefix}-{serial} not found on UPS Air Cargo.",
                    latency_ms=latency,
                )

            # ── Extract Header Info via regex ─────────────────────────
            origin = self._extract_regex(r'Origin:.*?<strong>\s*(\w+)\s*</strong>', html)
            destination = self._extract_regex(r'Destination:.*?<strong>\s*(\w+)\s*</strong>', html)
            booked_pcs = self._extract_int(r'Booked:\s*(\d+)\s*Pieces', html)
            received_pcs = self._extract_int(r'Received:\s*(\d+)\s*Pieces', html)
            most_recent = self._extract_regex(r'Most Recent Activity:</strong>\s*(.*?)\s*<', html)

            # Use received pieces if available, else booked
            pieces = received_pcs or booked_pcs

            # ── Parse TrackDataTable ──────────────────────────────────
            parser = _TableParser()
            parser.feed(html)

            events = []
            track_table = None
            for t in parser.tables:
                if t["id"] == "TrackDataTable":
                    track_table = t
                    break

            if track_table:
                for row in track_table["rows"]:
                    # Skip header row
                    if "Status" in row and "Station" in row:
                        continue
                    if len(row) >= 5:
                        evt = self._parse_event_row(row)
                        if evt:
                            events.append(evt)

            # Reverse to chronological order (UPS shows newest first)
            events.reverse()

            # ── Overall Status ────────────────────────────────────────
            overall_status = "Booked"
            if events:
                last_status = events[-1].get("status_message", "").lower()
                # Strip asterisk from "Booked *"
                last_status = last_status.rstrip(" *")
                overall_status = STATUS_MAP.get(last_status, "In Transit")

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
                    "weight": None,
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
                weight=None,
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "UPS Air Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin": origin,
                    "destination": destination,
                    "booked_pieces": booked_pcs,
                    "received_pieces": received_pcs,
                    "most_recent_activity": most_recent,
                },
            )

        except Exception as exc:
            logger.error(f"UPS Air Cargo: Failed to parse HTML: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse UPS Air Cargo response: {exc}",
                latency_ms=latency,
            )

    # ── Event Row Parser ──────────────────────────────────────────────

    def _parse_event_row(self, row: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse a single row from the TrackDataTable.
        Columns: Status | Station | Flight# | Pieces | Event Date/Time
        """
        try:
            status_raw = row[0].strip()
            station = row[1].strip()
            flight_raw = row[2].strip()
            pieces_raw = row[3].strip()
            datetime_raw = row[4].strip()

            # Clean status (remove asterisk from "Booked *")
            status_clean = status_raw.rstrip(" *").strip()

            # Map status to IATA code
            status_lower = status_clean.lower()
            status_code = "UNK"
            if "departed" in status_lower:
                status_code = "DEP"
            elif "arrived" in status_lower:
                status_code = "ARR"
            elif "received" in status_lower:
                status_code = "RCS"
            elif "delivered" in status_lower:
                status_code = "DLV"
            elif "booked" in status_lower:
                status_code = "BKD"
            elif "notified" in status_lower:
                status_code = "NFD"

            # Parse pieces
            evt_pieces = None
            try:
                evt_pieces = int(pieces_raw)
            except ValueError:
                pass

            # Extract flight number from flight column
            # Format: "UPS009  09/04/2026   SZX - BLR" or "UPS009 09/04/2026"
            flight_info = None
            flight_match = re.match(r'([A-Z]+\d+)', flight_raw)
            if flight_match:
                flight_info = flight_match.group(1)

            # Extract route from flight column
            route_match = re.search(r'(\w{3})\s*-\s*(\w{3})', flight_raw)
            board_point = route_match.group(1) if route_match else None
            off_point = route_match.group(2) if route_match else None

            # Parse event datetime: "09/04/2026 07:04" -> ISO format
            event_time = self._parse_datetime(datetime_raw)

            return {
                "station": station,
                "station_name": None,
                "status_code": status_code,
                "status_message": status_clean,
                "event_time": event_time,
                "flight_info": flight_info,
                "board_point": board_point,
                "off_point": off_point,
                "pieces": evt_pieces,
                "weight": None,
                "raw_status": status_raw,
            }
        except Exception as exc:
            logger.warning(f"UPS Air Cargo: Failed to parse row {row}: {exc}")
            return None

    # ── Utility Methods ───────────────────────────────────────────────

    @staticmethod
    def _parse_datetime(dt_str: str) -> Optional[str]:
        """Parse UPS datetime format: '09/04/2026 07:04' -> ISO string."""
        if not dt_str:
            return None
        try:
            import datetime
            # Format: MM/DD/YYYY HH:MM or MM/DD/YYYY
            parts = dt_str.strip().split(" ")
            date_parts = parts[0].split("/")
            if len(date_parts) == 3:
                month = int(date_parts[0])
                day = int(date_parts[1])
                year = int(date_parts[2])
                hour = 0
                minute = 0
                if len(parts) > 1 and ":" in parts[1]:
                    time_parts = parts[1].split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                dt = datetime.datetime(year, month, day, hour, minute)
                return dt.isoformat()
        except Exception:
            pass
        return dt_str

    @staticmethod
    def _extract_regex(pattern: str, html: str) -> Optional[str]:
        """Extract first regex match group from HTML."""
        match = re.search(pattern, html)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_int(pattern: str, html: str) -> Optional[int]:
        """Extract integer from first regex match group."""
        match = re.search(pattern, html)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None
