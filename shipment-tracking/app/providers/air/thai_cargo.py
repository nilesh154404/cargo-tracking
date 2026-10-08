"""
Thai Cargo (TG / prefix 217) provider.

Uses the CHORUS/SkyChain system at chorus.thaicargo.com.
No authentication required — guest user access via Tapestry form POST.
No Playwright / browser needed.

Two-step flow:
    1. GET  /skychain/app?service=page/nwp:Trackshipmt  (session cookie)
    2. POST /skychain/app  (Tapestry form data with AWB prefix+serial)
    Returns HTML page with Summary row + event tracking table.
"""

import re
import time
import logging
import datetime
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.thai_cargo")

# ── API Configuration ────────────────────────────────────────────────────
BASE_URL = "https://chorus.thaicargo.com"
APP_URL = f"{BASE_URL}/skychain/app"
TRACK_PAGE_URL = f"{APP_URL}?service=page/nwp:Trackshipmt"

TG_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# ── Tapestry Form Template ───────────────────────────────────────────────
FORM_FIELD_LIST = (
    "selectDoctype,txtPrefix,txtNumber,txtJrn,"
    "txtAWBPrefix,txtAWBNumber,"
    "txtAWBPrefix$0,txtAWBNumber$0,"
    "txtAWBPrefix$1,txtAWBNumber$1,"
    "txtAWBPrefix$2,txtAWBNumber$2,"
    "txtAWBPrefix$3,txtAWBNumber$3,"
    "txtAWBPrefix$4,txtAWBNumber$4,"
    "txtAWBPrefix$5,txtAWBNumber$5,"
    "txtAWBPrefix$6,txtAWBNumber$6,"
    "txtAWBPrefix$7,txtAWBNumber$7,"
    "$FormConditional,$JSubmit,$JSubmit$0,$JSubmit$1,$JSubmit$2,"
    "$FormConditional$0,$FormConditional$1,"
    "reload,pageSize,listSize,advSearch,trackViewHdn"
)

# ── Status Mapping ───────────────────────────────────────────────────────
STATUS_MAP = {
    "booked": "Booked",
    "booking confirmed": "Booked",
    "received from shipper": "Accepted",
    "manifested": "In Transit",
    "departed": "In Transit",
    "arrived": "Arrived",
    "received from flight": "Arrived",
    "documents delivered": "Arrived",
    "notified": "Arrived",
    "delivered": "Delivered",
    "transferred": "In Transit",
}

STATUS_CODE_MAP = {
    "booked": "BKD",
    "booking confirmed": "BKD",
    "received from shipper": "RCS",
    "manifested": "MAN",
    "departed": "DEP",
    "arrived": "ARR",
    "received from flight": "RCF",
    "documents delivered": "DOC",
    "notified": "NFD",
    "delivered": "DLV",
    "transferred": "TFD",
}

# ── Month Map ────────────────────────────────────────────────────────────
MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


class ThaiCargoProvider(BaseProvider):
    """
    Live provider for Thai Cargo (TG / prefix 217).
    Uses the CHORUS/SkyChain system with Tapestry framework form POST.

    Authentication flow (guest access — no login required):
        1. GET  /skychain/app?service=page/nwp:Trackshipmt  → session cookie
        2. POST /skychain/app  with Tapestry form data
        No OAuth, no JWT, no CAPTCHA, no Playwright.
    """

    name = "thai_cargo"
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

        if prefix != "217":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Thai Cargo (expects 217)",
                latency_ms=latency,
            )

        try:
            async with httpx.AsyncClient(
                timeout=25.0, verify=True, follow_redirects=True
            ) as client:
                # Step 1: GET track page to establish session
                logger.info(f"Thai Cargo: GET track page for session")
                await client.get(TRACK_PAGE_URL, headers=TG_HEADERS)

                # Step 2: POST tracking form
                form_data = self._build_form_data(prefix, serial)
                post_headers = {
                    **TG_HEADERS,
                    "content-type": "application/x-www-form-urlencoded",
                    "origin": BASE_URL,
                    "referer": TRACK_PAGE_URL,
                }

                logger.info(f"Thai Cargo: POST tracking for {prefix}-{serial}")
                resp = await client.post(APP_URL, data=form_data, headers=post_headers)

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"Thai Cargo HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            return self._parse_html(resp.text, prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Thai Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to Thai Cargo: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Thai Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error tracking Thai Cargo shipment: {exc}",
                latency_ms=latency,
            )

    # ── Form Builder ──────────────────────────────────────────────────

    @staticmethod
    def _build_form_data(prefix: str, serial: str) -> Dict[str, str]:
        """Build the Tapestry framework form data for tracking."""
        return {
            "service": "direct/1/nwp:Trackshipmt/trackForm",
            "sp": "S1",
            "Form1": FORM_FIELD_LIST,
            "trackForm_hdnLastPermissionCheck": "",
            "trackForm_hdnLastPermissionCode": "",
            "hdnFormID": "trackForm",
            "hdnbpval2": "false",
            "selectDoctype": "AWB",
            "txtPrefix": prefix,
            "txtNumber": serial,
            "txtJrn": "",
            "$FormConditional": "F",
            "$JSubmit": "Track",
            "$JSubmit$0": "Track",
            "$FormConditional$0": "F",
            "$FormConditional$1": "F",
            "reload": "",
            "pageSize": "10",
            "listSize": "0",
            "advSearch": "F",
            "trackViewHdn": "tableRadio",
        }

    # ── HTML Parsing ──────────────────────────────────────────────────

    def _parse_html(
        self,
        html: str,
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the Thai Cargo CHORUS tracking response HTML."""
        try:
            # Check for tracking results
            awb_pattern = f"{prefix}[-/]{serial}"
            if not re.search(awb_pattern, html):
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"AWB {prefix}-{serial} not found on Thai Cargo.",
                    latency_ms=latency,
                )

            # ── Summary Row ───────────────────────────────────────────
            # Pattern: [+/-] | 217-09545561 | CCU | MUC | 47 | 686.00 | 3.76 | LEATHER WALLETS | General Freight
            origin = None
            destination = None
            pieces = None
            weight_val = None
            volume_val = None
            goods_desc = None
            product = None

            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I)
            for row in rows:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
                if cells and len(cells) >= 8:
                    clean = [self._clean_cell(c) for c in cells]
                    if prefix in str(clean) and serial in str(clean):
                        # Summary row found
                        # Cols: [expand] | AWB | Origin | Dest | Pieces | Weight | Volume | Goods | Product | SHC
                        for i, c in enumerate(clean):
                            if re.match(r'^[A-Z]{3}$', c) and origin is None:
                                origin = c
                                if i + 1 < len(clean) and re.match(r'^[A-Z]{3}$', clean[i + 1]):
                                    destination = clean[i + 1]
                                break
                        # Extract numeric fields after origin/dest
                        for c in clean:
                            if pieces is None and re.match(r'^\d+$', c):
                                pieces = int(c)
                            elif weight_val is None and re.match(r'^[\d.]+$', c) and float(c) > 10:
                                weight_val = float(c)
                            elif volume_val is None and re.match(r'^[\d.]+$', c) and float(c) < 100:
                                volume_val = float(c)
                        # Goods description (longer text field)
                        for c in clean:
                            if len(c) > 5 and not re.match(r'^[\d.]+$', c) and c not in (origin, destination, f"{prefix}-{serial}"):
                                if goods_desc is None:
                                    goods_desc = c
                                elif product is None:
                                    product = c
                        break

            # ── Event Table ───────────────────────────────────────────
            # Find tracking table by looking for header row
            events = []
            header_idx = html.find(">Station<")
            if header_idx < 0:
                header_idx = html.find(">Station")

            if header_idx > 0:
                table_start = html.rfind("<table", 0, header_idx)
                table_end = html.find("</table>", header_idx)
                if table_start > 0 and table_end > 0:
                    table_html = html[table_start:table_end + 8]
                    table_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.S | re.I)

                    for tr in table_rows:
                        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)
                        if len(cells) >= 6:
                            clean = [self._clean_cell(c) for c in cells]
                            # Skip header row
                            if clean[0] == "Station":
                                continue
                            evt = self._parse_event_row(clean)
                            if evt:
                                events.append(evt)

            # Reverse to chronological order (newest first in HTML)
            events.reverse()

            # ── Overall Status ────────────────────────────────────────
            overall_status = "Booked"
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
                volume=volume_val,
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "Thai Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin": origin,
                    "destination": destination,
                    "goods_description": goods_desc,
                    "product": product,
                },
            )

        except Exception as exc:
            logger.error(f"Thai Cargo: Failed to parse HTML: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse Thai Cargo response: {exc}",
                latency_ms=latency,
            )

    # ── Event Row Parser ──────────────────────────────────────────────

    def _parse_event_row(self, cells: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse a single event row from the CHORUS tracking table.
        Columns: Station | Status Date | Status | Flight Details | Pieces | Weight
        """
        try:
            station = cells[0].strip()
            date_str = cells[1].strip()
            status = cells[2].strip()
            flight_details = cells[3].strip()
            pieces_str = cells[4].strip()
            weight_str = cells[5].strip().replace("K", "").strip()

            if not station or station == "-":
                return None

            # Parse status
            status_lower = status.lower()
            status_code = STATUS_CODE_MAP.get(status_lower, "UNK")

            # Parse datetime: "21 SEP 2026 15:14"
            event_time = self._parse_chorus_datetime(date_str)

            # Parse pieces
            evt_pieces = None
            try:
                evt_pieces = int(pieces_str)
            except ValueError:
                pass

            # Parse weight
            evt_weight = None
            try:
                evt_weight = float(weight_str)
            except ValueError:
                pass

            # Parse flight info: "TG0924, 20 SEP 2026, ATD 00:50, BKK-MUC, STA - 20 SEP 2026 - 07:05"
            flight_number = None
            board_point = None
            off_point = None

            if flight_details and flight_details != "-":
                flight_match = re.match(r'(\w+\d+)', flight_details)
                if flight_match:
                    flight_number = flight_match.group(1)
                route_match = re.search(r'([A-Z]{3})-([A-Z]{3})', flight_details)
                if route_match:
                    board_point = route_match.group(1)
                    off_point = route_match.group(2)

            return {
                "station": station,
                "station_name": None,
                "status_code": status_code,
                "status_message": status,
                "event_time": event_time,
                "flight_info": flight_number,
                "flight_details": flight_details if flight_details != "-" else None,
                "board_point": board_point,
                "off_point": off_point,
                "pieces": evt_pieces,
                "weight": evt_weight,
                "raw_status": status,
            }
        except Exception as exc:
            logger.warning(f"Thai Cargo: Failed to parse event row {cells}: {exc}")
            return None

    # ── Utilities ─────────────────────────────────────────────────────

    @staticmethod
    def _clean_cell(html_content: str) -> str:
        """Remove HTML tags and &nbsp; from cell content."""
        text = re.sub(r'<[^>]+>', '', html_content)
        text = text.replace('&nbsp;', '').replace('\xa0', '')
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _parse_chorus_datetime(dt_str: str) -> Optional[str]:
        """Parse CHORUS datetime: '21 SEP 2026 15:14' -> ISO string."""
        if not dt_str:
            return None
        try:
            parts = dt_str.strip().split()
            if len(parts) >= 3:
                day = int(parts[0])
                month = MONTH_MAP.get(parts[1].upper(), 1)
                year = int(parts[2])
                hour = 0
                minute = 0
                if len(parts) >= 4 and ":" in parts[3]:
                    time_parts = parts[3].split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                dt = datetime.datetime(year, month, day, hour, minute)
                return dt.isoformat()
        except Exception:
            pass
        return dt_str
