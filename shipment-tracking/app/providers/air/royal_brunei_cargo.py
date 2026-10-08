"""
Royal Brunei Airlines Cargo (BI / prefix 672) provider.

Uses the CargoSpot HTML form at flyroyalbrunei.com.
No authentication required — simple HTML form POST + table parsing.
No Playwright / browser needed.

Single-step flow:
    POST /rba/cargospot/index.php  (form-encoded: cd, awb, button=Search)
    Returns HTML page with Summary table + Details table.
"""

import re
import time
import logging
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.royal_brunei")

# ── API Configuration ────────────────────────────────────────────────────
CARGOSPOT_URL = "https://www.flyroyalbrunei.com/rba/cargospot/index.php"

RB_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.flyroyalbrunei.com",
    "referer": "https://www.flyroyalbrunei.com/rba/cargospot/index.php",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# ── Status Mapping ───────────────────────────────────────────────────────
STATUS_MAP = {
    "booked": "Booked",
    "received": "Accepted",
    "received from flight": "Arrived",
    "manifested": "In Transit",
    "departed": "In Transit",
    "arrived": "Arrived",
    "delivered": "Delivered",
    "notified": "Arrived",
    "transferred": "In Transit",
}


# ── HTML Table Parser ────────────────────────────────────────────────────
class _TableParser(HTMLParser):
    """Lightweight parser to extract <table> data from CargoSpot HTML."""

    def __init__(self):
        super().__init__()
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self.tables: List[List[List[str]]] = []
        self._cur_table: List[List[str]] = []
        self._cur_row: List[str] = []
        self._cur_cell = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table = True
            self._cur_table = []
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._cur_row = []
        elif tag == "td" and self._in_row:
            self._in_cell = True
            self._cur_cell = ""

    def handle_endtag(self, tag):
        if tag == "td" and self._in_cell:
            self._in_cell = False
            self._cur_row.append(self._cur_cell.strip())
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._cur_row:
                self._cur_table.append(self._cur_row)
        elif tag == "table" and self._in_table:
            self._in_table = False
            if self._cur_table:
                self.tables.append(self._cur_table)

    def handle_data(self, data):
        if self._in_cell:
            self._cur_cell += data


class RoyalBruneiCargoProvider(BaseProvider):
    """
    Live provider for Royal Brunei Airlines Cargo (BI / prefix 672).
    Uses the CargoSpot HTML tracking page — simple form POST.

    Authentication flow (none required):
        POST /rba/cargospot/index.php  with cd=<prefix>&awb=<serial>&button=Search
        No OAuth, no JWT, no cookies, no Playwright.
    """

    name = "royal_brunei_cargo"
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

        if prefix != "672":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Royal Brunei Cargo (expects 672)",
                latency_ms=latency,
            )

        form_data = {
            "cd": prefix,
            "awb": serial,
            "button": "Search",
        }

        try:
            async with httpx.AsyncClient(
                timeout=20.0, verify=True, follow_redirects=True
            ) as client:
                logger.info(f"Royal Brunei: POST {CARGOSPOT_URL} for {prefix}-{serial}")
                resp = await client.post(CARGOSPOT_URL, data=form_data, headers=RB_HEADERS)

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"Royal Brunei CargoSpot HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            return self._parse_html(resp.text, prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Royal Brunei cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to Royal Brunei CargoSpot: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Royal Brunei tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error tracking Royal Brunei shipment: {exc}",
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
        """Parse the CargoSpot HTML response into a ProviderResult."""
        try:
            parser = _TableParser()
            parser.feed(html)

            if len(parser.tables) < 1:
                # No tables found — AWB probably not found
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"AWB {prefix}-{serial} not found on Royal Brunei CargoSpot.",
                    latency_ms=latency,
                )

            # ── Summary Table (Table 1) ──────────────────────────────
            # Header: AWB Number | Origin | Destination | Pieces | Weight
            summary_table = parser.tables[0]
            origin = None
            destination = None
            pieces = None
            weight_val = None

            if len(summary_table) >= 2:
                # First row is header, second is data
                data_row = summary_table[1] if len(summary_table[0]) >= 3 else summary_table[0]
                # Try to find the data row (the one with actual AWB number)
                for row in summary_table:
                    if any(prefix in cell for cell in row):
                        data_row = row
                        break

                if len(data_row) >= 5:
                    origin = data_row[1].strip() if data_row[1].strip() else None
                    destination = data_row[2].strip() if data_row[2].strip() else None
                    try:
                        pieces = int(data_row[3].strip())
                    except (ValueError, IndexError):
                        pass
                    try:
                        weight_val = float(data_row[4].strip())
                    except (ValueError, IndexError):
                        pass

            # ── Details Table (Table 2) ───────────────────────────────
            # Header: From | To | Flight | Status | Dep Date | Dep Time | Arr Date | Arr Time | Pieces | Weight
            events = []
            overall_status = "Booked"

            if len(parser.tables) >= 2:
                details_table = parser.tables[1]
                # Skip header row(s)
                for row in details_table:
                    # Skip header rows
                    if "From" in row or "Status" in row:
                        continue
                    if len(row) >= 8:
                        evt = self._parse_detail_row(row)
                        if evt:
                            events.append(evt)

            # Determine overall status from last event
            if events:
                last_status = events[-1].get("status_message", "").lower()
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
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "Royal Brunei Airlines Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin": origin,
                    "destination": destination,
                    "summary_table": parser.tables[0] if parser.tables else [],
                    "details_table": parser.tables[1] if len(parser.tables) >= 2 else [],
                },
            )

        except Exception as exc:
            logger.error(f"Royal Brunei: Failed to parse HTML: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse Royal Brunei CargoSpot response: {exc}",
                latency_ms=latency,
            )

    # ── Row Parser ────────────────────────────────────────────────────

    def _parse_detail_row(self, row: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse a single detail row from the CargoSpot table.
        Columns: From | To | Flight | Status | Dep Date | Dep Time | Arr Date | Arr Time | Pieces | Weight
        """
        try:
            from_station = row[0].strip()
            to_station = row[1].strip()
            flight = row[2].strip()
            status = row[3].strip()
            dep_date = row[4].strip()
            dep_time = row[5].strip()
            arr_date = row[6].strip() if len(row) > 6 else ""
            arr_time = row[7].strip() if len(row) > 7 else ""
            evt_pieces = None
            evt_weight = None

            if len(row) > 8:
                try:
                    evt_pieces = int(row[8].strip())
                except (ValueError, IndexError):
                    pass
            if len(row) > 9:
                try:
                    evt_weight = float(row[9].strip())
                except (ValueError, IndexError):
                    pass

            # Build event time from departure date/time
            event_time = self._parse_cargospot_datetime(dep_date, dep_time)
            arrival_time = self._parse_cargospot_datetime(arr_date, arr_time)

            # Map status to code
            status_lower = status.lower()
            status_code = "UNK"
            if "departed" in status_lower:
                status_code = "DEP"
            elif "arrived" in status_lower:
                status_code = "ARR"
            elif "received from flight" in status_lower:
                status_code = "RCF"
            elif "received" in status_lower:
                status_code = "RCS"
            elif "manifested" in status_lower:
                status_code = "MAN"
            elif "delivered" in status_lower:
                status_code = "DLV"
            elif "booked" in status_lower:
                status_code = "BKD"
            elif "notified" in status_lower:
                status_code = "NFD"
            elif "transferred" in status_lower:
                status_code = "TFD"

            return {
                "station": from_station,
                "station_name": None,
                "status_code": status_code,
                "status_message": status,
                "event_time": event_time,
                "arrival_time": arrival_time,
                "flight_info": flight if flight else None,
                "board_point": from_station,
                "off_point": to_station,
                "pieces": evt_pieces,
                "weight": evt_weight,
                "raw_status": status,
            }
        except Exception as exc:
            logger.warning(f"Royal Brunei: Failed to parse detail row {row}: {exc}")
            return None

    # ── Date/Time Parsing ─────────────────────────────────────────────

    @staticmethod
    def _parse_cargospot_datetime(date_str: str, time_str: str) -> Optional[str]:
        """
        Parse CargoSpot date/time format: '08SEP26' + '14:15' → ISO string.
        """
        if not date_str or not time_str:
            return None

        try:
            # Format: DDMMMYY (e.g. 08SEP26)
            import datetime

            month_map = {
                "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
                "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
                "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
            }

            day = int(date_str[:2])
            month_str = date_str[2:5].upper()
            year_short = int(date_str[5:])
            month = month_map.get(month_str, 1)

            # Handle 2-digit year (assume 2000s)
            year = 2000 + year_short if year_short < 100 else year_short

            # Parse time
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0

            dt = datetime.datetime(year, month, day, hour, minute)
            return dt.isoformat()

        except Exception:
            return f"{date_str} {time_str}"
