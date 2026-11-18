import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult
from app.services.location_matcher import match_location

logger = logging.getLogger("shipment_tracking.providers.maersk")

MAERSK_TRACKING_URL = "https://api.maersk.com/synergy/tracking"

CONSUMER_KEY = os.environ.get(
    "MAERSK_CONSUMER_KEY",
    "UtMm6JCDcGTnMGErNGvS2B98kt1Wl25H",
)

AKAMAI_BM_TELEMETRY = os.environ.get("MAERSK_AKAMAI_TELEMETRY", "")

MAERSK_BASE_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "api-version": "v2",
    "consumer-key": CONSUMER_KEY,
    "origin": "https://www.maersk.com",
    "priority": "u=1, i",
    "referer": "https://www.maersk.com/",
    "sec-ch-ua": '"Not-A.Brand";v="99", "Google Chrome";v="157", "Chromium";v="157"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
    ),
}

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

MAERSK_MILESTONE_MAP = [
    ("GATE-OUT", ("E012", "Empty Equipment Dispatched")),
    ("GATE-IN", ("E040", "Gate In to Outbound Terminal")),
    ("LOAD", ("E058", "Loaded on Vessel")),
    ("CONTAINER DEPARTURE", ("E061", "Vessel Departure")),
    ("VESSEL-DEPARTURE", ("E061", "Vessel Departure")),
    ("DEPARTURE", ("E061", "Vessel Departure")),
    ("CONTAINER ARRIVAL", ("E080", "Vessel Arrival")),
    ("VESSEL-ARRIVAL", ("E080", "Vessel Arrival")),
    ("ARRIVAL", ("E080", "Vessel Arrival")),
    ("DISCHARG", ("E089", "Discharged from Vessel")),
    ("DISCHARGE", ("E089", "Discharged from Vessel")),
    ("TRANSSHIPMENT-DISCHARGE", ("E089", "Transshipment Discharged")),
    ("TRANSSHIPMENT-LOAD", ("E090", "Transshipment Loaded")),
    ("DELIVERY", ("E106", "Gate Out from Inbound Terminal for Delivery to Consignee")),
    ("EMPTY-RETURN", ("E138", "Empty Container Returned from Customer")),
]


def _parse_maersk_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return str(date_str)


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
        **kwargs: Any,
    ) -> ProviderResult:
        start_time = time.time()

        cntr_input = (
            kwargs.get("container_no")
            or kwargs.get("cntr_no")
            or ""
        ).strip().upper()

        bkg_input = (
            kwargs.get("mawb_obl_no")
            or kwargs.get("booking_no")
            or kwargs.get("billing_no")
            or kwargs.get("bl_no")
            or ""
        ).strip().upper()

        target_container = cntr_input or (tracking_number.strip().upper() if len(tracking_number) >= 10 and tracking_number[:4].isalpha() else "")

        if bkg_input:
            query_id = bkg_input
        elif target_container:
            query_id = target_container
        else:
            query_id = tracking_number.strip().upper() or f"{prefix}{serial}".strip().upper()

        operator = OPERATOR_MAP.get(prefix.upper(), "MAEU")

        try:
            headers = dict(MAERSK_BASE_HEADERS)
            telemetry = os.environ.get("MAERSK_AKAMAI_TELEMETRY", AKAMAI_BM_TELEMETRY)
            if telemetry:
                headers["akamai-bm-telemetry"] = telemetry

            url = f"{MAERSK_TRACKING_URL}/{query_id}"
            params = {"operator": operator}
            curl_cmd = self.build_curl_command("GET", f"{url}?operator={operator}", headers=headers)

            data = None
            response_text = None
            latency = 0.0

            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(url, params=params, headers=headers)
                    latency = round((time.time() - start_time) * 1000, 2)
                    response_text = resp.text

                    if resp.status_code == 200:
                        data = resp.json()
                    elif resp.status_code == 403:
                        logger.info(f"Maersk API returned 403 for {query_id}. Falling back to browser session...")
                    elif resp.status_code == 404:
                        return ProviderResult(
                            success=False,
                            provider_name=self.name,
                            status_code=404,
                            error=f"No tracking data found for query {query_id} on Maersk",
                            request_curl=curl_cmd,
                            response_body=response_text,
                            latency_ms=latency,
                        )
            except Exception as e:
                logger.debug(f"Direct Maersk request note: {e}")

            if not data:
                data = await self._track_via_browser(query_id)
                latency = round((time.time() - start_time) * 1000, 2)

            if not data:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"No tracking data found for query {query_id} on Maersk",
                    request_curl=curl_cmd,
                    response_body=response_text,
                    latency_ms=latency,
                )

            containers = data.get("containers", [])
            target_container_obj = None

            if containers:
                if target_container:
                    for c in containers:
                        c_num = (c.get("container_num") or "").strip().upper()
                        if c_num == target_container:
                            target_container_obj = c
                            break
                if not target_container_obj:
                    target_container_obj = containers[0]

            if not target_container_obj:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"Container {target_container} not found in Maersk response for {query_id}",
                    request_curl=curl_cmd,
                    response_body=response_text,
                    latency_ms=latency,
                    raw_data=data,
                )

            final_container_no = (target_container_obj.get("container_num") or target_container or query_id).strip().upper()

            origin_obj = data.get("origin") or {}
            orig_city = origin_obj.get("city") or origin_obj.get("terminal") or data.get("origin_name") or ""
            orig_country = origin_obj.get("country") or ""
            origin = f"{orig_city}, {orig_country}".strip(", ") if orig_country else orig_city

            dest_obj = data.get("destination") or {}
            dest_city = dest_obj.get("city") or dest_obj.get("terminal") or data.get("destination_name") or ""
            dest_country = dest_obj.get("country") or ""
            destination = f"{dest_city}, {dest_country}".strip(", ") if dest_country else dest_city

            raw_locations = target_container_obj.get("locations", [])
            raw_events: List[Dict[str, Any]] = []

            for location in raw_locations:
                loc_name = location.get("city") or location.get("terminal") or location.get("name", "")
                loc_country = location.get("country") or ""
                terminal = location.get("terminal") or ""
                loc_code = location.get("location_code")

                if terminal and loc_country:
                    station_str = f"{loc_name}, {loc_country} ({terminal})"
                elif loc_country:
                    station_str = f"{loc_name}, {loc_country}"
                else:
                    station_str = loc_name

                events = location.get("events", [])
                for ev in events:
                    activity = (ev.get("activity") or ev.get("event") or "Status Update").strip()
                    event_date_raw = ev.get("event_time") or ev.get("actual_time") or ev.get("expected_time") or ev.get("date")
                    iso_time = _parse_maersk_date(event_date_raw) or datetime.now(timezone.utc).isoformat()
                    vessel = ev.get("vessel_name")
                    voyage = ev.get("voyage_num") or ""

                    if vessel and voyage:
                        flight_info = f"{final_container_no} | {vessel} (Voyage {voyage})"
                    elif vessel:
                        flight_info = f"{final_container_no} | {vessel}"
                    else:
                        flight_info = final_container_no

                    act_upper = activity.upper()
                    status_code = "INFO"
                    status_msg = activity
                    for kw, (code, canonical_msg) in MAERSK_MILESTONE_MAP:
                        if kw in act_upper:
                            status_code = code
                            status_msg = canonical_msg
                            break

                    time_type = (ev.get("event_time_type") or "").upper()
                    if time_type == "ACTUAL":
                        raw_status = "ACTUAL"
                    elif time_type in ("EXPECTED", "ESTIMATED"):
                        raw_status = "ESTIMATED"
                    else:
                        try:
                            dt_check = datetime.fromisoformat(str(iso_time).replace("Z", "+00:00"))
                            raw_status = "ESTIMATED" if dt_check > datetime.now(timezone.utc) else "ACTUAL"
                        except Exception:
                            raw_status = "ACTUAL"

                    coords = (
                        match_location(loc_code, "SEA")
                        or match_location(station_str, "SEA")
                        or match_location(loc_name, "SEA")
                    )

                    raw_events.append({
                        "station": station_str,
                        "status_code": status_code,
                        "status_message": status_msg,
                        "event_time": iso_time,
                        "flight_info": flight_info,
                        "pieces": 1,
                        "weight": 28000.0,
                        "raw_status": raw_status,
                        "coordinates": coords,
                    })

            if not raw_events:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"No milestone events found for container {final_container_no} on Maersk",
                    request_curl=curl_cmd,
                    response_body=response_text,
                    latency_ms=latency,
                    raw_data=data,
                )

            actual_events = [e for e in raw_events if e["raw_status"] == "ACTUAL"]
            active_target = actual_events[-1] if actual_events else raw_events[-1]

            for e in raw_events:
                is_act = (e is active_target)
                e["active"] = is_act
                e["is_active"] = is_act

            raw_events.sort(key=lambda x: x.get("event_time") or "", reverse=True)

            final_status = "In Transit"
            if active_target:
                code = active_target.get("status_code")
                if code in ("E106", "E138", "DLV"):
                    final_status = "Delivered"
                elif code in ("E089", "DISCH"):
                    final_status = "Discharged"
                elif code in ("E040", "GT_IN"):
                    final_status = "Gate In to Outbound Terminal"
                elif code in ("E058", "E061", "E090", "LOAD"):
                    final_status = "In Transit"

            container_type = target_container_obj.get("container_type") or target_container_obj.get("iso_code") or ""
            container_size = target_container_obj.get("container_size") or ""

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=final_status,
                origin=origin or (raw_events[-1]["station"] if raw_events else None),
                destination=destination or (raw_events[0]["station"] if raw_events else None),
                pieces=1,
                weight={"unit": "kg", "value": 28000.0},
                volume=76.2 if "40" in container_size or "40" in container_type else 33.2,
                events=raw_events,
                latest_event=active_target,
                raw_data={
                    "carrier": "Maersk",
                    "container_number": final_container_no,
                    "billing_no": data.get("tpdoc_num") or query_id,
                    "container_type": container_type,
                    "container_size": container_size,
                    "events_count": len(raw_events),
                    "source": "Maersk Synergy Tracking API v2",
                },
                request_curl=curl_cmd,
                response_body=response_text,
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

    async def _track_via_browser(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Fallback browser session to bypass Akamai Bot Manager using local Chrome."""
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
                    ],
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
                done_event = asyncio.Event()

                async def handle_response(response):
                    url = response.url
                    if "synergy/tracking" in url:
                        try:
                            content_type = response.headers.get("content-type", "")
                            if "json" in content_type:
                                body = await response.json()
                                if body and isinstance(body, dict) and "containers" in body:
                                    captured["data"] = body
                                    done_event.set()
                        except Exception:
                            pass

                page.on("response", handle_response)

                nav_url = f"https://www.maersk.com/tracking/{query_id}"
                try:
                    await page.goto(nav_url, wait_until="domcontentloaded", timeout=40000)
                except Exception as e:
                    logger.debug(f"Maersk browser navigation notice: {e}")

                try:
                    await asyncio.wait_for(done_event.wait(), timeout=20.0)
                except asyncio.TimeoutError:
                    pass

                await browser.close()
                return captured.get("data")
        except Exception as exc:
            logger.error(f"Error during Maersk browser tracking fallback: {exc}")
            return None
