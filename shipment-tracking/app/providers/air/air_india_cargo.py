import json
import base64
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.air_india_cargo")

PORTAL_URL = "https://aicargoportal.airindia.com/icargoneoportal/app/main/"
GRAPHQL_URL = "https://aicargoportal.airindia.com/portalgateway/graphql"

# GraphQL query extracted from the live Air India Cargo portal
TRACKING_QUERY = """fragment ShipmentFragment on TrackingItem {
  awb_number
  pieces
  stated_weight
  stated_volume
  special_handling_code
  product_name
  shipment_description
  origin_airport_code
  destination_airport_code
  milestones {
    milestone
    status
    __typename
  }
  departure_time
  departure_time_postfix
  arrival_time
  arrival_time_postfix
  transit_stations {
    number_of_flights
    stops
    __typename
  }
  units_of_measure {
    weight
    volume
    __typename
  }
  __typename
}

query GetShipmentsByAwbs($shipmentNumbers: [String]!) {
  GetShipmentsByAwbs(shipmentNumbers: $shipmentNumbers) {
    ...ShipmentFragment
    __typename
  }
}
"""

# GraphQL mutation to get anonymous guest token (replaces Playwright)
LOGIN_MUTATION = """mutation loginAsAnonymousUser {
  loginAsAnonymousUser {
    security {
      id_token
    }
  }
}
"""

GRAPHQL_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,hi;q=0.8",
    "content-type": "application/json",
    "cptoken": "null",
    "trigger-point": "undefined",
    "origin": "https://aicargoportal.airindia.com",
    "referer": "https://aicargoportal.airindia.com/icargoneoportal/app/main/",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
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

# ── Cookie Cache ─────────────────────────────────────────────────────────
_ai_cookie_cache: Dict[str, Any] = {
    "cookie_string": None,
    "expires_at": 0.0,
}


class AirIndiaCargoProvider(BaseProvider):
    """
    Live provider for Air India Cargo (AI / prefix 098).
    Uses the iCargo Neo Portal GraphQL API at aicargoportal.airindia.com.

    Authentication flow (pure httpx, no Playwright):
        1. GET the portal page to establish AWSALB session cookies.
        2. POST the loginAsAnonymousUser GraphQL mutation to get the JWT
           (id_token) which is also set as ICO-NEO-PORTAL-Authorization cookie.
        3. POST the tracking GraphQL query using the combined cookie string.
    """

    name = "air_india_cargo"
    mode = "AIR"

    async def _get_auth_cookies(self, force_refresh: bool = False) -> Optional[str]:
        """
        Obtain the JWT token + AWSALB cookies via pure httpx calls.
        No browser needed — uses the loginAsAnonymousUser GraphQL mutation.
        """
        now = time.time()

        # Return cached cookies if still valid (120s safety buffer)
        if (
            not force_refresh
            and _ai_cookie_cache["cookie_string"]
            and now < _ai_cookie_cache["expires_at"] - 120
        ):
            logger.debug("AirIndia: Using cached auth cookies")
            return _ai_cookie_cache["cookie_string"]

        try:
            logger.info("AirIndia: Obtaining token via loginAsAnonymousUser (no browser)...")
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0, verify=True
            ) as client:
                # Step 1: Hit portal page to get initial AWSALB session cookies
                await client.get(PORTAL_URL, headers={"user-agent": GRAPHQL_HEADERS["user-agent"]})

                # Step 2: Call loginAsAnonymousUser mutation to get JWT
                login_payload = {
                    "operationName": "loginAsAnonymousUser",
                    "query": LOGIN_MUTATION,
                    "variables": {},
                }
                resp = await client.post(
                    GRAPHQL_URL, json=login_payload, headers=GRAPHQL_HEADERS
                )
                resp.raise_for_status()
                data = resp.json()

                # Extract id_token from response
                id_token = (
                    data.get("data", {})
                    .get("loginAsAnonymousUser", {})
                    .get("security", {})
                    .get("id_token")
                )

                if not id_token:
                    logger.warning("AirIndia: loginAsAnonymousUser did not return an id_token.")
                    return None

                # Build the cookie string: JWT + AWSALB cookies from the httpx jar
                awsalb = client.cookies.get("AWSALB", "")
                awsalbcors = client.cookies.get("AWSALBCORS", "")
                cookie_string = (
                    f"ICO-NEO-PORTAL-Authorization={id_token}"
                    f"; AWSALB={awsalb}"
                    f"; AWSALBCORS={awsalbcors}"
                )

                # Cache the cookie string (iCargo tokens typically last ~30 min)
                _ai_cookie_cache["cookie_string"] = cookie_string
                _ai_cookie_cache["expires_at"] = now + 1800  # 30-minute cache
                logger.info("AirIndia: Successfully obtained auth token (no browser).")
                return cookie_string

        except Exception as exc:
            logger.error(f"AirIndia: Failed to get auth cookies: {exc}")
            return None

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        awb_number = f"{prefix}{serial}"

        try:
            # ── Step 1: Get Auth Cookies via loginAsAnonymousUser ─────
            cookie_string = await self._get_auth_cookies(force_refresh=force_refresh)
            if not cookie_string:
                latency = round((time.time() - start_time) * 1000, 2)
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=401,
                    error="Air India Cargo: Unable to obtain auth token via loginAsAnonymousUser.",
                    latency_ms=latency,
                )

            # ── Step 2: Execute GraphQL tracking query ────────────────
            logger.info(f"AirIndia: Querying GraphQL for AWB {prefix}-{serial}...")
            graphql_payload = {
                "operationName": "GetShipmentsByAwbs",
                "query": TRACKING_QUERY,
                "variables": {"shipmentNumbers": [awb_number]},
            }

            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30.0, verify=True
            ) as client:
                resp = await client.post(
                    GRAPHQL_URL,
                    json=graphql_payload,
                    headers={**GRAPHQL_HEADERS, "cookie": cookie_string},
                )

                # Handle 401 – try once with force-refreshed token
                if resp.status_code == 401 and not force_refresh:
                    logger.info("AirIndia: Got 401, retrying with fresh auth cookies...")
                    cookie_string = await self._get_auth_cookies(force_refresh=True)
                    if cookie_string:
                        resp = await client.post(
                            GRAPHQL_URL,
                            json=graphql_payload,
                            headers={**GRAPHQL_HEADERS, "cookie": cookie_string},
                        )

                resp.raise_for_status()
                latency = round((time.time() - start_time) * 1000, 2)

                # ── Step 3: Parse the JSON response ───────────────────
                data = resp.json()
                return self._parse_graphql_response(
                    data=data,
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
                error="Air India Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"AirIndia HTTP error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code,
                error=str(exc),
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"AirIndia tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    # ── Response Parsing ─────────────────────────────────────────────────

    def _parse_graphql_response(
        self,
        data: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the Air India GraphQL JSON response."""

        # Check for GraphQL-level errors
        if "errors" in data and data["errors"]:
            error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
            logger.warning(f"AirIndia GraphQL error: {error_msg}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=502,
                error=error_msg,
                latency_ms=latency,
            )

        shipments = (data.get("data") or {}).get("GetShipmentsByAwbs")
        if not shipments or len(shipments) == 0:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=404,
                status="NOT_FOUND",
                error=f"No tracking data found for AWB {prefix}-{serial} on Air India Cargo.",
                latency_ms=latency,
            )

        shipment = shipments[0]

        # ── Extract basic shipment info ───────────────────────────────
        origin = shipment.get("origin_airport_code")
        destination = shipment.get("destination_airport_code")
        pieces = shipment.get("pieces")
        stated_weight = shipment.get("stated_weight")
        stated_volume = shipment.get("stated_volume")

        # Determine weight unit from units_of_measure
        uom = shipment.get("units_of_measure") or {}
        weight_unit = "kg" if uom.get("weight") == "K" else "lb"

        # ── Parse milestones into events ──────────────────────────────
        milestones_raw = shipment.get("milestones") or []
        events = self._build_events_from_milestones(
            milestones=milestones_raw,
            shipment=shipment,
        )

        # ── Determine overall status ──────────────────────────────────
        status = self._determine_status(milestones_raw)

        # ── Parse departure / arrival times ───────────────────────────
        departure_time = self._parse_ai_datetime(
            shipment.get("departure_time")
        )
        arrival_time = self._parse_ai_datetime(
            shipment.get("arrival_time")
        )

        # Build latest event
        latest_event = events[-1] if events else None

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=status,
            origin=origin,
            destination=destination,
            pieces=pieces,
            weight={"value": stated_weight, "unit": weight_unit} if stated_weight else None,
            volume=stated_volume,
            events=events,
            latest_event=latest_event,
            raw_data={
                "carrier": "Air India Cargo",
                "awb": f"{prefix}-{serial}",
                "product_name": shipment.get("product_name"),
                "shipment_description": shipment.get("shipment_description"),
                "special_handling_code": shipment.get("special_handling_code"),
                "departure_time": departure_time,
                "departure_time_postfix": shipment.get("departure_time_postfix"),
                "arrival_time": arrival_time,
                "arrival_time_postfix": shipment.get("arrival_time_postfix"),
                "transit_stations": shipment.get("transit_stations"),
            },
            latency_ms=latency,
        )

    def _build_events_from_milestones(
        self,
        milestones: List[Dict[str, Any]],
        shipment: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Build event list from Air India milestone objects.
        Each milestone has: { "milestone": "ACCEPTED", "status": "done" }
        """
        events = []
        origin = shipment.get("origin_airport_code", "")
        destination = shipment.get("destination_airport_code", "")

        for ms in milestones:
            milestone_name = ms.get("milestone", "").upper()
            milestone_status = ms.get("status", "")

            status_code = self._milestone_to_fsu(milestone_name)
            station = self._milestone_to_station(
                milestone_name, origin, destination
            )
            event_time = self._milestone_to_time(milestone_name, shipment)
            status_message = self._milestone_to_description(milestone_name)

            events.append({
                "station": station,
                "status_code": status_code,
                "status_message": status_message,
                "event_time": event_time,
                "milestone_status": milestone_status,
                "raw_status": milestone_name,
            })

        return events

    @staticmethod
    def _milestone_to_fsu(milestone: str) -> str:
        """Map Air India milestone names to standard FSU status codes."""
        mapping = {
            "ACCEPTED": "RCS",
            "DEPARTED": "DEP",
            "ARRIVED": "ARR",
            "DELIVERED": "DLV",
            "BOOKED": "BKD",
            "MANIFESTED": "MAN",
            "RECEIVED": "RCF",
            "NOTIFIED": "NFD",
            "TRANSFERRED": "TFD",
            "CHECKED IN": "RCS",
        }
        return mapping.get(milestone, milestone)

    @staticmethod
    def _milestone_to_station(
        milestone: str, origin: str, destination: str
    ) -> str:
        """Determine which station the milestone pertains to."""
        origin_milestones = {"ACCEPTED", "BOOKED", "MANIFESTED", "DEPARTED"}
        destination_milestones = {"ARRIVED", "DELIVERED", "NOTIFIED", "RECEIVED"}

        if milestone in origin_milestones:
            return origin
        elif milestone in destination_milestones:
            return destination
        return ""

    @staticmethod
    def _milestone_to_description(milestone: str) -> str:
        """Human-readable description for each milestone."""
        descriptions = {
            "ACCEPTED": "Shipment accepted at origin",
            "DEPARTED": "Departed from origin",
            "ARRIVED": "Arrived at destination",
            "DELIVERED": "Delivered to consignee",
            "BOOKED": "Booking confirmed",
            "MANIFESTED": "Manifested on flight",
            "RECEIVED": "Received from flight",
            "NOTIFIED": "Consignee notified",
        }
        return descriptions.get(milestone, milestone.title())

    def _milestone_to_time(
        self, milestone: str, shipment: Dict[str, Any]
    ) -> Optional[str]:
        """
        Extract the most relevant timestamp for a given milestone.
        Air India provides departure_time and arrival_time at shipment level.
        """
        if milestone in ("ACCEPTED", "BOOKED", "MANIFESTED", "DEPARTED"):
            return self._parse_ai_datetime(shipment.get("departure_time"))
        elif milestone in ("ARRIVED", "RECEIVED", "NOTIFIED", "DELIVERED"):
            return self._parse_ai_datetime(shipment.get("arrival_time"))
        return None

    @staticmethod
    def _parse_ai_datetime(dt_str: Optional[str]) -> Optional[str]:
        """
        Parse Air India datetime formats into ISO 8601.
        Known formats: 'DD-MM-YYYY HH:MM:SS', 'DD-MM-YYYY HH:MM'
        """
        if not dt_str:
            return None
        for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                return datetime.strptime(dt_str.strip(), fmt).isoformat()
            except ValueError:
                continue
        return dt_str

    @staticmethod
    def _determine_status(milestones: List[Dict[str, Any]]) -> str:
        """Determine overall shipment status from milestones."""
        last_done = None
        for ms in milestones:
            if ms.get("status") == "done":
                last_done = ms.get("milestone", "").upper()
        status_map = {
            "DELIVERED": "Delivered",
            "ARRIVED": "Arrived",
            "DEPARTED": "In Transit",
            "ACCEPTED": "Accepted",
            "BOOKED": "Booked",
        }
        return status_map.get(last_done, "Unknown") if last_done else "Unknown"
