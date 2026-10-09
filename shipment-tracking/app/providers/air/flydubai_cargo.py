import json
import base64
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.flydubai_cargo")

# ── Accelya Platform URLs ────────────────────────────────────────────────
PORTAL_URL = "https://prdonofz.accelya.io/app/offerandorder/#/home/find-offer"
SEARCH_URL = "https://prdonofz.accelya.io/api/order/services/cargo/v1/orders/actions/search?view=summary"
ORDER_URL_BASE = "https://prdonofz.accelya.io/api/order/services/cargo/v1/orders/b"

# OAuth guest token endpoint (discovered from the Angular main.js bundle)
GUEST_TOKEN_URL = "https://prdonofz.accelya.io/api/uaa/guest/oauth/token"
# base64("mercator:") — hardcoded in the Angular app as SERVICE_AUTHORIZATION_CODE
OAUTH_BASIC_AUTH = "bWVyY2F0b3I6"

API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,hi;q=0.8",
    "content-type": "application/json",
    "app-id": "OO002",
    "origin": "https://prdonofz.accelya.io",
    "referer": "https://prdonofz.accelya.io/app/offerandorder/",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand);v="99"',
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

# ── Token + Cookie Cache ─────────────────────────────────────────────────
_fz_cache: Dict[str, Any] = {
    "bearer_token": None,
    "expires_at": 0.0,
}


def _parse_jwt_expiry(jwt_token: str) -> Optional[float]:
    """Extract the 'exp' claim from a JWT payload (epoch seconds)."""
    try:
        payload_b64 = jwt_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        decoded = base64.b64decode(payload_b64)
        data = json.loads(decoded)
        return float(data.get("exp", 0))
    except Exception:
        return None


class FlyDubaiCargoProvider(BaseProvider):
    """
    Live provider for FlyDubai Cargo (FZ / prefix 141).
    Uses the Accelya (Mercator) Offer & Order REST API at prdonofz.accelya.io.

    Authentication flow (pure httpx, no Playwright):
        1. POST to /api/uaa/guest/oauth/token with mercator client credentials
           to get a guest Bearer token.
        2. POST /orders/actions/search → finds the order by AWB
        3. GET  /orders/b{reference}  → gets full milestone detail
    """

    name = "flydubai_cargo"
    mode = "AIR"

    # ── Token Acquisition via direct OAuth ────────────────────────────

    async def _get_token(self, force_refresh: bool = False) -> Optional[Dict[str, str]]:
        """
        Obtain the OAuth guest token via direct POST to /api/uaa/guest/oauth/token.
        No browser needed — uses the same client credentials the Angular SPA uses.
        """
        now = time.time()

        # Return cached token if still valid (120s buffer)
        if (
            not force_refresh
            and _fz_cache["bearer_token"]
            and now < _fz_cache["expires_at"] - 120
        ):
            logger.debug("FlyDubaiCargo: Using cached Accelya token")
            return {"bearer": _fz_cache["bearer_token"]}

        try:
            logger.info("FlyDubaiCargo: Obtaining guest token via OAuth (no browser)...")
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0, verify=True
            ) as client:
                resp = await client.post(
                    GUEST_TOKEN_URL,
                    content="tenant=FZ&client_id=mercator&client_secret=",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {OAUTH_BASIC_AUTH}",
                        "user-agent": API_HEADERS["user-agent"],
                    },
                    params={
                        "productName": "offerandorder",
                        "_time": str(int(time.time() * 1000)),
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                access_token = data.get("access_token")
                if not access_token:
                    logger.warning("FlyDubaiCargo: OAuth response missing access_token.")
                    return None

                exp = _parse_jwt_expiry(access_token)
                _fz_cache["bearer_token"] = access_token
                _fz_cache["expires_at"] = exp or (now + 1800)
                logger.info(
                    "FlyDubaiCargo: Successfully obtained Accelya guest token (no browser). "
                    f"Expires at {datetime.fromtimestamp(exp).isoformat() if exp else 'unknown'}."
                )
                return {"bearer": access_token}

        except Exception as exc:
            logger.error(f"FlyDubaiCargo: Failed to get guest token: {exc}")
            return None

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
        awb_full = f"{prefix}{serial}"  # e.g. "14153681191"

        try:
            # ── Step 1: Get Bearer Token via OAuth ───────────────
            token_data = await self._get_token(force_refresh=force_refresh)
            if not token_data:
                latency = round((time.time() - start_time) * 1000, 2)
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=401,
                    error="FlyDubai Cargo: Unable to obtain Accelya guest token.",
                    latency_ms=latency,
                )

            headers = {
                **API_HEADERS,
                "authorization": f"Bearer {token_data['bearer']}",
            }

            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30.0, verify=True
            ) as client:

                # ── Step 2: Search for the order by AWB ───────────────
                search_payload = {
                    "orderFilter": {
                        "airCapacity": {
                            "documentNumbers": [awb_full],
                            "includeItinerary": False,
                        }
                    },
                    "pageRequest": {"page": 1, "pageSize": 10},
                }

                logger.info(f"FlyDubaiCargo: Searching for AWB {prefix}-{serial}...")
                resp = await client.post(SEARCH_URL, json=search_payload, headers=headers)

                # Handle 401 – retry with fresh token
                if resp.status_code == 401 and not force_refresh:
                    logger.info("FlyDubaiCargo: Got 401, retrying with fresh token...")
                    token_data = await self._get_token(force_refresh=True)
                    if token_data:
                        headers["authorization"] = f"Bearer {token_data['bearer']}"
                        resp = await client.post(
                            SEARCH_URL, json=search_payload, headers=headers
                        )

                resp.raise_for_status()
                search_data = resp.json()

                # Extract booking reference from search result
                booking_ref = self._extract_booking_ref(search_data)
                if not booking_ref:
                    latency = round((time.time() - start_time) * 1000, 2)
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error=(
                            f"No shipment records found for {prefix}-{serial} "
                            f"on FlyDubai Cargo. Please verify the tracking number."
                        ),
                        latency_ms=latency,
                    )

                # ── Step 3: Get full order details with milestones ────
                logger.info(
                    f"FlyDubaiCargo: Fetching order details for ref {booking_ref}..."
                )
                detail_url = f"{ORDER_URL_BASE}{booking_ref}"
                resp2 = await client.get(detail_url, headers=headers)
                resp2.raise_for_status()
                order_data = resp2.json()

                latency = round((time.time() - start_time) * 1000, 2)
                return self._parse_order_response(
                    order_data=order_data,
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
                error="FlyDubai Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"FlyDubaiCargo HTTP error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code,
                error=str(exc),
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"FlyDubaiCargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_booking_ref(search_data: Dict[str, Any]) -> Optional[str]:
        """Extract the booking reference number from search API response."""
        try:
            orders = (search_data.get("data") or {}).get("order", [])
            if not orders:
                return None
            order = orders[0]
            items = (order.get("orderItems") or {}).get("orderItem", [])
            if not items:
                return None
            ref = (items[0].get("reference") or {}).get("bookingReferenceNumber")
            return ref
        except (IndexError, KeyError, TypeError):
            return None

    # ── Response Parsing ─────────────────────────────────────────────

    def _parse_order_response(
        self,
        order_data: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the Accelya order detail response into a ProviderResult."""

        try:
            data = order_data.get("data", {})
            items = (data.get("orderItems") or {}).get("orderItem", [])
            if not items:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"No order items found for {prefix}-{serial}.",
                    latency_ms=latency,
                )

            item = items[0]
            air_cap = (item.get("productInfo") or {}).get("airCapacity", {})

            # ── Basic shipment info ───────────────────────────────────
            origin_info = air_cap.get("origin") or {}
            dest_info = air_cap.get("destination") or {}
            origin = origin_info.get("code")
            destination = dest_info.get("code")

            # Quantity
            cargo_info = air_cap.get("cargoInfo") or {}
            qty_list = cargo_info.get("quantityInfo") or []
            pieces = None
            weight_val = None
            volume_val = None
            if qty_list:
                qty = qty_list[0]
                pieces = qty.get("piece")
                w = qty.get("weight") or {}
                weight_val = w.get("value")
                v = qty.get("volume") or {}
                volume_val = v.get("value")

            # ── Milestones → Events ───────────────────────────────────
            fulfillment = item.get("fulfillmentInfo") or {}
            service_info = fulfillment.get("serviceInfo") or {}
            milestones = service_info.get("milestone") or []

            events = self._build_events(milestones)

            # ── Overall status from latest milestone ──────────────────
            status = self._determine_status(milestones)

            # ── Itinerary info ────────────────────────────────────────
            itinerary_info = (air_cap.get("offerItinerary") or {}).get("itinerary", [])
            flight_legs = self._build_flight_legs(itinerary_info)

            # Latest event
            latest_event = events[0] if events else None

            # Is it a part shipment?
            is_part = item.get("isPartShipment", False)

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=status,
                origin=origin,
                destination=destination,
                pieces=pieces,
                weight={"value": weight_val, "unit": "kg"} if weight_val else None,
                volume=volume_val,
                events=events,
                latest_event=latest_event,
                raw_data={
                    "carrier": "FlyDubai Cargo",
                    "awb": f"{prefix}-{serial}",
                    "origin_name": origin_info.get("name"),
                    "destination_name": dest_info.get("name"),
                    "commodity": cargo_info.get("goodsDescription"),
                    "product": (air_cap.get("product") or {}).get("product", {}).get("name"),
                    "service_type": (air_cap.get("product") or {}).get("service", {}).get("description"),
                    "is_part_shipment": is_part,
                    "flight_legs": flight_legs,
                    "routes": air_cap.get("routes", []),
                },
                latency_ms=latency,
            )
        except Exception as exc:
            logger.error(f"FlyDubaiCargo parse error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Failed to parse FlyDubai Cargo response: {exc}",
                latency_ms=latency,
            )

    def _build_events(self, milestones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build event list from Accelya milestones.
        Each milestone has rich data: code, description, station, statusDate, statusData.
        Events are sorted newest-first (most recent at index 0).
        """
        events = []

        for ms in milestones:
            code_info = ms.get("code") or {}
            status_code = code_info.get("code", "")
            description = code_info.get("description", "")

            station_info = ms.get("station") or {}
            station = station_info.get("code", "")

            status_date = ms.get("statusDate") or {}
            achieved = status_date.get("achieved")
            event_time = self._parse_accelya_datetime(achieved)

            # Extract quantity for this specific event
            status_data = ms.get("statusData") or {}
            qty = status_data.get("quantity") or {}
            event_pieces = qty.get("piece")
            event_weight = (qty.get("weight") or {}).get("value")

            # Extract flight info from itinerary data if present
            itin = status_data.get("itinerary") or {}
            transport = itin.get("transportInfo") or {}
            flight_number = None
            if transport.get("carrier") and transport.get("number"):
                flight_number = f"{transport['carrier']}-{transport['number']}"

            board_point = (itin.get("boardPoint") or {}).get("code")
            off_point = (itin.get("offPoint") or {}).get("code")

            # On-time status
            delay_info = ms.get("delayOntime") or {}
            on_time = delay_info.get("description")

            events.append({
                "station": station,
                "status_code": status_code,
                "status_message": description,
                "event_time": event_time,
                "pieces": event_pieces,
                "weight": event_weight,
                "flight_number": flight_number,
                "board_point": board_point,
                "off_point": off_point,
                "on_time_status": on_time,
                "raw_status": status_code,
                "is_latest": ms.get("latestMilestone", False),
            })

        # Sort by event_time descending (newest first)
        events.sort(
            key=lambda e: e.get("event_time") or "0000",
            reverse=True,
        )

        return events

    @staticmethod
    def _build_flight_legs(itinerary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract flight leg information from the itinerary."""
        legs = []
        for leg in itinerary:
            transport = leg.get("transportInfo") or {}
            dep_local = leg.get("departureDateTimeLocal") or {}
            arr_local = leg.get("arrivalDateTimeLocal") or {}
            movement = leg.get("movementStatus") or {}
            space = leg.get("spaceStatus") or {}
            qty = leg.get("quantity") or {}

            legs.append({
                "leg_number": leg.get("legNumber"),
                "board_point": (leg.get("boardPoint") or {}).get("code"),
                "off_point": (leg.get("offPoint") or {}).get("code"),
                "carrier": transport.get("carrier"),
                "flight_number": f"{transport.get('carrier', '')}-{transport.get('number', '')}",
                "scheduled_departure": dep_local.get("schedule"),
                "actual_departure": dep_local.get("actual"),
                "scheduled_arrival": arr_local.get("schedule"),
                "actual_arrival": arr_local.get("actual"),
                "aircraft": (transport.get("vehicle") or {}).get("registrationNumber"),
                "aircraft_type": ((transport.get("vehicle") or {}).get("type") or {}).get("code"),
                "movement_status": movement.get("code"),
                "space_status": space.get("description"),
                "pieces": qty.get("piece"),
                "weight": (qty.get("weight") or {}).get("value"),
                "is_part_shipment": leg.get("partIndicator", False),
                "is_interline": leg.get("oalIndicator", False),
            })

        return legs

    @staticmethod
    def _determine_status(milestones: List[Dict[str, Any]]) -> str:
        """Determine overall shipment status from the latest milestone."""
        # Find the milestone marked as latestMilestone
        for ms in milestones:
            if ms.get("latestMilestone"):
                code = (ms.get("code") or {}).get("code", "")
                return _ACCELYA_STATUS_MAP.get(code, code)

        # Fallback: use the first milestone (usually sorted newest-first)
        if milestones:
            code = (milestones[0].get("code") or {}).get("code", "")
            return _ACCELYA_STATUS_MAP.get(code, code)

        return "Unknown"

    @staticmethod
    def _parse_accelya_datetime(dt_str: Optional[str]) -> Optional[str]:
        """
        Parse Accelya datetime formats into ISO 8601.
        Known format: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM'
        """
        if not dt_str:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(dt_str.strip(), fmt).isoformat()
            except ValueError:
                continue
        return dt_str


# ── Accelya milestone code → human-readable status mapping ───────────────
_ACCELYA_STATUS_MAP: Dict[str, str] = {
    "BKD": "Booked",
    "RCS": "Accepted",
    "RCT": "Received from Carrier",
    "MAN": "Manifested",
    "DEP": "In Transit",
    "ARR": "Arrived",
    "RCF": "Received at Destination",
    "NFD": "Notified",
    "DLV": "Delivered",
    "CCD": "Customs Cleared",
    "AWD": "Documentation Complete",
    "AWR": "Documentation Received",
    "CRC": "Customs Released",
    "DDL": "Delivered (Door)",
    "DIS": "Discrepancy",
    "FOH": "Freight on Hand",
    "TRM": "Transferred",
    "PRE": "Prepared for Loading",
}
