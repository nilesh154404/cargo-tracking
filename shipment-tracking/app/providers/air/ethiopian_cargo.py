"""
Ethiopian Airlines Cargo (ET / prefix 071) provider.

Uses the public tracking page at ethiopiancargo.azurewebsites.net.
No authentication required — simple HTML form POST.
No Playwright / browser needed.

Single-step flow:
    POST /my-cargo/track-your-shipment/Index/  (form-encoded: AirwayBilNum)
    Returns HTML page with Summary card + event timeline.
"""

import re
import time
import logging
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.ethiopian_cargo")

# ── API Configuration ────────────────────────────────────────────────────
BASE_URL = "https://ethiopiancargo.azurewebsites.net"
TRACKING_URL = f"{BASE_URL}/my-cargo/track-your-shipment/Index/"

ET_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "content-type": "application/x-www-form-urlencoded",
    "origin": BASE_URL,
    "referer": TRACKING_URL,
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# ── Status Mapping ───────────────────────────────────────────────────────
STATUS_MAP = {
    "booked": "Booked",
    "accepted": "Accepted",
    "manifested on flight": "In Transit",
    "departed on flight": "In Transit",
    "received from flight": "Arrived",
    "consignee/agent notified of arrival": "Arrived",
    "delivered": "Delivered",
    "transferred": "In Transit",
}

STATUS_CODE_MAP = {
    "booked": "BKD",
    "accepted": "RCS",
    "manifested on flight": "MAN",
    "departed on flight": "DEP",
    "received from flight": "RCF",
    "consignee/agent notified of arrival": "NFD",
    "delivered": "DLV",
    "transferred": "TFD",
}


class EthiopianCargoProvider(BaseProvider):
    """
    Live provider for Ethiopian Airlines Cargo (ET / prefix 071).
    Uses the public tracking page via HTML form POST.

    Authentication flow (none required):
        POST /my-cargo/track-your-shipment/Index/
        with AirwayBilNum=<serial_number>
        No OAuth, no JWT, no reCAPTCHA enforcement, no Playwright.
    """

    name = "ethiopian_cargo"
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

        if prefix != "071":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Ethiopian Cargo (expects 071)",
                latency_ms=latency,
            )

        try:
            async with httpx.AsyncClient(
                timeout=20.0, verify=True, follow_redirects=True
            ) as client:
                # GET first to establish session cookie
                logger.info(f"Ethiopian Cargo: Establishing session for {prefix}-{serial}")
                await client.get(TRACKING_URL, headers={"user-agent": ET_HEADERS["user-agent"]})

                # POST with AWB number (just the serial, no prefix)
                logger.info(f"Ethiopian Cargo: POST tracking for {serial}")
                resp = await client.post(
                    TRACKING_URL,
                    data={"AirwayBilNum": serial},
                    headers=ET_HEADERS,
                )

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"Ethiopian Cargo HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            return self._parse_html(resp.text, prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Ethiopian Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to Ethiopian Cargo: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Ethiopian Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error tracking Ethiopian Cargo shipment: {exc}",
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
        """Parse the Ethiopian Cargo tracking page HTML."""
        try:
            # Check if tracking data is present
            if "AWB No" not in html:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"AWB {prefix}-{serial} not found on Ethiopian Cargo.",
                    latency_ms=latency,
                )

            # ── Summary Info ──────────────────────────────────────────
            origin = self._re_first(r'<p[^>]*>Origin</p>\s*<p[^>]*>(\w{3})</p>', html)
            destination = self._re_first(r'<p[^>]*>Destination</p>\s*<p[^>]*>(\w{3})</p>', html)
            pieces_str = self._re_first(r'<p[^>]*>Pieces</p>\s*<p[^>]*>(\d+)\s*Pcs</p>', html)
            weight_str = self._re_first(r'<p[^>]*>Weight</p>\s*<p[^>]*>([\d.]+)\s*Kg', html)

            pieces = int(pieces_str) if pieces_str else None
            weight_val = float(weight_str) if weight_str else None

            # ── Route (flight legs) ───────────────────────────────────
            legs = re.findall(r'<h4\s+class="step-title">(\w{3})</h4>', html)

            # ── Flight info per leg ───────────────────────────────────
            # Pattern: "ET3695 • 2026-09-13"
            flight_legs = re.findall(
                r'class="[^"]*(?:flight|tracking)[^"]*"[^>]*>\s*(\w+\d+)\s*.\s*(\d{4}-\d{2}-\d{2})',
                html, re.S | re.I
            )

            # ── Events ────────────────────────────────────────────────
            # Pattern matches: "Status_text pieces_info | volume | weight | route"
            event_sections = re.findall(
                r'class="[^"]*(?:tracking-list-item-status|status-heading)[^"]*"[^>]*>\s*(.*?)\s*</(?:div|span|p|h\d)',
                html, re.S | re.I
            )

            # Better: extract from the detail sections found earlier
            detail_sections = re.findall(
                r'class="[^"]*(?:tracking|flight|status|event)[^"]*"[^>]*>\s*(.*?)\s*</(?:div|span|p|td)',
                html, re.S | re.I
            )

            events = self._build_events(detail_sections, legs)

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
                latest_event=latest_event,
                events=events,
                latency_ms=latency,
                raw_data={
                    "carrier": "Ethiopian Airlines Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin": origin,
                    "destination": destination,
                    "route": legs,
                    "flight_legs": [
                        {"flight": f[0], "date": f[1]} for f in flight_legs
                    ] if flight_legs else [],
                },
            )

        except Exception as exc:
            logger.error(f"Ethiopian Cargo: Failed to parse HTML: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse Ethiopian Cargo response: {exc}",
                latency_ms=latency,
            )

    # ── Event Builder ─────────────────────────────────────────────────

    def _build_events(
        self, detail_sections: List[str], legs: List[str]
    ) -> List[Dict[str, Any]]:
        """Build structured events from the parsed detail sections."""
        events = []
        current_station = None
        current_flight = None

        for section in detail_sections:
            clean = re.sub(r'<[^>]+>', ' ', section).strip()
            clean = re.sub(r'\s+', ' ', clean)

            if not clean or len(clean) < 2:
                continue

            # Station header: "HYD →" or "ADD →"
            station_match = re.match(r'^([A-Z]{3})\s*→?$', clean)
            if station_match:
                current_station = station_match.group(1)
                continue

            # Flight info: "ET3695 • 2026-09-13"
            flight_match = re.match(r'^([A-Z]{2}\d+)\s*.\s*(\d{4}-\d{2}-\d{2})$', clean)
            if flight_match:
                current_flight = flight_match.group(1)
                continue

            # Status line: "Delivered" or "Delivered 4/4 Pcs | 0.75 m 3 | 312.0 Kg | from ADD to ABV"
            status_match = re.match(
                r'^(Booked|Accepted|Manifested on Flight|Departed on Flight|Received From Flight|'
                r'Consignee/Agent notified of arrival|Delivered|Transferred)\s*(.*)',
                clean, re.I
            )
            if status_match:
                status_text = status_match.group(1).strip()
                details_text = status_match.group(2).strip()

                # Parse details: "4/4 Pcs | 0.75 m 3 | 312.0 Kg | from HYD to ADD"
                evt_pieces = None
                evt_weight = None
                from_station = current_station
                to_station = None

                pcs_match = re.search(r'(\d+)/(\d+)\s*Pcs', details_text)
                if pcs_match:
                    evt_pieces = int(pcs_match.group(1))

                wt_match = re.search(r'([\d.]+)\s*Kg', details_text)
                if wt_match:
                    evt_weight = float(wt_match.group(1))

                route_match = re.search(r'from\s+(\w{3})\s+to\s+(\w{3})', details_text, re.I)
                if route_match:
                    from_station = route_match.group(1)
                    to_station = route_match.group(2)

                status_lower = status_text.lower()
                status_code = STATUS_CODE_MAP.get(status_lower, "UNK")

                events.append({
                    "station": from_station,
                    "station_name": None,
                    "status_code": status_code,
                    "status_message": status_text,
                    "event_time": None,  # Not available per-event in HTML
                    "flight_info": current_flight,
                    "board_point": from_station,
                    "off_point": to_station,
                    "pieces": evt_pieces,
                    "weight": evt_weight,
                    "raw_status": status_text,
                })

        # Reverse events (HTML shows newest first)
        events.reverse()
        return events

    # ── Utility ───────────────────────────────────────────────────────

    @staticmethod
    def _re_first(pattern: str, text: str) -> Optional[str]:
        """Return first regex match group or None."""
        m = re.search(pattern, text, re.S | re.I)
        return m.group(1).strip() if m else None
