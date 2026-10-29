import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.maersk")

MAERSK_TRACKING_URL = "https://api.maersk.com/synergy/tracking"

# Consumer key for the Maersk Synergy API (can be overridden via env var)
CONSUMER_KEY = os.environ.get(
    "MAERSK_CONSUMER_KEY",
    "UtMm6JCDcGTnMGErNGvS2B98kt1Wl25H",
)

# Akamai BM telemetry — session-bound, refresh via env var when expired
AKAMAI_BM_TELEMETRY = os.environ.get("MAERSK_AKAMAI_TELEMETRY", "")

MAERSK_BASE_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "api-version": "v2",
    "consumer-key": CONSUMER_KEY,
    "origin": "https://www.maersk.com",
    "priority": "u=1, i",
    "referer": "https://www.maersk.com/",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# Operator code mapping based on container prefix
OPERATOR_MAP = {
    "MAEU": "MAEU",
    "MRSU": "MAEU",
    "MSKU": "MAEU",
    "MRKU": "MAEU",
    "APMU": "MAEU",
    "MNBU": "MAEU",
    "HASU": "MAEU",
    "SUDU": "MAEU",
}

# Event code mapping for Maersk milestones
EVENT_CODE_MAP = {
    "LOAD": "LOAD",
    "GATE-IN": "GT_IN",
    "GATE-OUT": "GT_OUT",
    "DISCHARGE": "DISCH",
    "STUFFING": "STUFF",
    "STRIPPING": "STRIP",
    "RAIL-DEPARTURE": "RAIL_DEP",
    "RAIL-ARRIVAL": "RAIL_ARR",
    "VESSEL-DEPARTURE": "DEP",
    "VESSEL-ARRIVAL": "ARR",
    "TRANSSHIPMENT-DISCHARGE": "TS_DISCH",
    "TRANSSHIPMENT-LOAD": "TS_LOAD",
    "CUSTOMS-RELEASE": "CUSTOMS",
    "DELIVERY": "DLV",
    "EMPTY-RETURN": "MT_RET",
    "CONTAINER-ARRIVAL": "CNT_ARR",
    "CONTAINER-DEPARTURE": "CNT_DEP",
}


def _resolve_event_code(activity: str) -> str:
    """Map Maersk activity type to a standard event code."""
    activity_upper = (activity or "").upper()
    for key, code in EVENT_CODE_MAP.items():
        if key in activity_upper:
            return code
    return "INFO"


def _determine_overall_status(events: List[Dict]) -> str:
    """Determine the overall shipment status from the last event."""
    if not events:
        return "Unknown"

    last_event = events[-1]
    code = last_event.get("status_code", "")
    msg = (last_event.get("raw_status") or "").upper()

    if code in ("DLV", "MT_RET") or "DELIVER" in msg or "EMPTY" in msg:
        return "Delivered"
    elif code in ("DEP", "LOAD", "TS_LOAD", "RAIL_DEP", "CNT_DEP"):
        return "In Transit"
    elif code in ("ARR", "DISCH", "TS_DISCH", "RAIL_ARR", "CNT_ARR"):
        return "Arrived"
    elif code in ("GT_IN", "CUSTOMS"):
        return "In Terminal"
    elif code in ("GT_OUT",):
        return "Gate Out"
    else:
        return "In Transit"


class MaerskProvider(BaseProvider):
    """
    Maersk Direct API provider using the Synergy Tracking v2 endpoint.
    Provides rich container tracking data including vessel info, routing,
    and detailed milestone events directly from Maersk's platform.
    """

    name = "maersk"
    mode = "SEA"

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        container_id = f"{prefix}{serial}".upper().strip()
        operator = OPERATOR_MAP.get(prefix.upper(), "MAEU")

        try:
            headers = dict(MAERSK_BASE_HEADERS)

            # Add Akamai telemetry if available
            telemetry = os.environ.get("MAERSK_AKAMAI_TELEMETRY", AKAMAI_BM_TELEMETRY)
            if telemetry:
                headers["akamai-bm-telemetry"] = telemetry

            url = f"{MAERSK_TRACKING_URL}/{container_id}"
            params = {"operator": operator}

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url, params=params, headers=headers)
                latency = round((time.time() - start_time) * 1000, 2)

                if resp.status_code == 403:
                    logger.warning(
                        f"Maersk API returned 403 (Akamai block) for {container_id}. "
                        "Attempting browser fallback via Playwright..."
                    )
                    data = await self._track_via_browser(container_id)
                    if not data:
                        return ProviderResult(
                            success=False,
                            provider_name=self.name,
                            status_code=403,
                            error=(
                                f"Maersk API returned 403 Forbidden for container {container_id}. "
                                "Akamai bot protection blocked the request. "
                                "Please refresh the MAERSK_AKAMAI_TELEMETRY environment variable."
                            ),
                            latency_ms=latency,
                        )
                elif resp.status_code == 404:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        error=f"No tracking data found for container {container_id} on Maersk",
                        latency_ms=latency,
                    )
                elif resp.status_code != 200:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=resp.status_code,
                        error=f"Maersk API returned HTTP {resp.status_code}: {resp.text[:300]}",
                        latency_ms=latency,
                    )
                else:
                    data = resp.json()

                # Parse containers array (API returns tracking for all containers in shipment)
                containers = data.get("containers", [])

                # Find matching container
                target_container = None
                for c in containers:
                    if c.get("container_num", "").upper() == container_id:
                        target_container = c
                        break
                if not target_container and containers:
                    target_container = containers[0]

                if not target_container:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        error=f"Container {container_id} not found in Maersk response",
                        latency_ms=latency,
                        raw_data=data,
                    )

                # Extract origin, destination from top-level or container
                origin_info = data.get("origin", {})
                dest_info = data.get("destination", {})
                origin = origin_info.get("city") or origin_info.get("terminal") or data.get("origin_name")
                destination = dest_info.get("city") or dest_info.get("terminal") or data.get("destination_name")

                # Vessel info
                vessel_name = data.get("vessel_name") or data.get("vessel")

                # Parse events/milestones
                raw_events = target_container.get("locations", [])
                parsed_events: List[Dict[str, Any]] = []

                for location in raw_events:
                    loc_name = location.get("city") or location.get("terminal") or location.get("name", "")
                    loc_country = location.get("country") or ""
                    station_str = f"{loc_name}, {loc_country}" if loc_country else loc_name

                    events = location.get("events", [])
                    for ev in events:
                        activity = ev.get("activity") or ev.get("event") or "Status Update"
                        event_date = ev.get("date") or ev.get("expected_date") or ev.get("event_time")
                        vessel = ev.get("vessel_name") or vessel_name
                        voyage = ev.get("voyage_num") or ""

                        flight_info = None
                        if vessel:
                            flight_info = f"Vessel: {vessel}"
                            if voyage:
                                flight_info += f" / Voyage: {voyage}"

                        status_code = _resolve_event_code(activity)

                        parsed_events.append({
                            "station": station_str,
                            "status_code": status_code,
                            "status_message": activity,
                            "event_time": event_date,
                            "flight_info": flight_info,
                            "pieces": 1,
                            "weight": None,
                            "raw_status": activity,
                        })

                if not parsed_events:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        error=f"No milestone events found for container {container_id} on Maersk",
                        latency_ms=latency,
                        raw_data=data,
                    )

                # Set origin/destination from events if not in top-level
                if not origin and parsed_events:
                    origin = parsed_events[0]["station"]
                if not destination and parsed_events:
                    destination = parsed_events[-1]["station"]

                overall_status = _determine_overall_status(parsed_events)
                latest_event = parsed_events[-1]

                # Container details
                container_type = target_container.get("container_type") or target_container.get("iso_code") or ""
                container_size = target_container.get("container_size") or ""

                return ProviderResult(
                    success=True,
                    provider_name=self.name,
                    status_code=200,
                    status=overall_status,
                    origin=origin,
                    destination=destination,
                    pieces=1,
                    weight={"unit": "kg", "value": 28000.0},
                    volume=76.2 if "40" in container_size or "40" in container_type else 33.2,
                    events=parsed_events,
                    latest_event=latest_event,
                    raw_data={
                        "carrier": "Maersk Line",
                        "container_number": container_id,
                        "container_type": container_type,
                        "container_size": container_size,
                        "vessel_name": vessel_name,
                        "events_count": len(parsed_events),
                        "source": "Maersk Synergy Tracking API v2",
                    },
                    latency_ms=latency,
                )

        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Network error connecting to Maersk API: {exc}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to Maersk API: {str(exc)}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Unexpected error in Maersk provider: {exc}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Unexpected error parsing Maersk response: {str(exc)}",
                latency_ms=latency,
            )

    async def _track_via_browser(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Fallback browser session to bypass Akamai Bot Manager using Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed, skipping browser fallback.")
            return None

        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        executable_path = next((p for p in chrome_paths if os.path.exists(p)), None)

        try:
            async with async_playwright() as p:
                launch_kwargs = {
                    "headless": True,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                    ]
                }
                if executable_path:
                    launch_kwargs["executable_path"] = executable_path

                browser = await p.chromium.launch(**launch_kwargs)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()

                captured: Dict[str, Any] = {}

                async def handle_response(response):
                    url = response.url
                    if f"tracking/{container_id}" in url or f"tracking/{container_id.upper()}" in url:
                        try:
                            content_type = response.headers.get("content-type", "")
                            if "json" in content_type:
                                body = await response.json()
                                if body and isinstance(body, dict) and "containers" in body:
                                    captured["data"] = body
                        except Exception:
                            pass

                page.on("response", handle_response)

                nav_url = f"https://www.maersk.com/tracking/{container_id}"
                try:
                    await page.goto(nav_url, wait_until="networkidle", timeout=35000)
                except Exception as e:
                    logger.debug(f"Maersk browser navigation notice: {e}")

                # Wait for data interception
                for _ in range(6):
                    if "data" in captured:
                        break
                    await asyncio.sleep(1.0)

                await browser.close()
                return captured.get("data")
        except Exception as exc:
            logger.error(f"Error during Maersk browser tracking fallback: {exc}")
            return None
