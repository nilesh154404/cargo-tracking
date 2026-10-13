import json
import base64
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.emirates_skycargo")

# ── Emirates SkyCargo (Accelya / Mercator) Endpoints ─────────────────────
SEARCH_URL = "https://eskycargo.emirates.com/api/order/services/cargo/v1/orders/actions/search?view=summary"
ORDER_URL_BASE = "https://eskycargo.emirates.com/api/order/services/cargo/v1/orders/b"
GUEST_TOKEN_URL = "https://eskycargo.emirates.com/api/uaa/guest/oauth/token"
# base64("mercator:") — client credentials used by the web portal
OAUTH_BASIC_AUTH = "bWVyY2F0b3I6"

BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,hi;q=0.8",
    "adrum": "isAjax:true",
    "content-type": "application/json",
    "origin": "https://eskycargo.emirates.com",
    "referer": "https://eskycargo.emirates.com/app/offerandorder/",
    "sec-ch-ua": '"Google Chrome";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
    ),
}

_STATUS_MAP: Dict[str, str] = {
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

_token_cache: Dict[str, Any] = {
    "bearer_token": None,
    "expires_at": 0.0,
}


def _parse_jwt_expiry(jwt_token: str) -> Optional[float]:
    """Extract exp epoch from JWT payload."""
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


class EmiratesSkyCargoProvider(BaseProvider):
    name = "emirates_skycargo"
    mode = "AIR"

    async def _get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """Fetch fresh guest token dynamically via Accelya OAuth endpoint."""
        now = time.time()
        if (
            not force_refresh
            and _token_cache["bearer_token"]
            and now < _token_cache["expires_at"] - 120
        ):
            return _token_cache["bearer_token"]

        try:
            logger.info("Emirates SkyCargo: Requesting fresh guest token via OAuth...")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0, verify=False) as client:
                resp = await client.post(
                    GUEST_TOKEN_URL,
                    content="tenant=EK&client_id=mercator&client_secret=",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {OAUTH_BASIC_AUTH}",
                        "origin": BASE_HEADERS["origin"],
                        "referer": BASE_HEADERS["referer"],
                        "user-agent": BASE_HEADERS["user-agent"],
                    },
                    params={
                        "productName": "offerandorder",
                        "_time": str(int(time.time() * 1000)),
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("access_token")
                    if token:
                        exp = _parse_jwt_expiry(token)
                        _token_cache["bearer_token"] = token
                        _token_cache["expires_at"] = exp or (now + 1800)
                        logger.info("Emirates SkyCargo: Successfully fetched fresh guest OAuth token.")
                        return token
                    logger.warning("Emirates SkyCargo: OAuth response missing access_token.")
                else:
                    logger.error(f"Emirates SkyCargo: OAuth token returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            logger.error(f"Emirates SkyCargo: Token acquisition exception: {exc}")

        return None

    async def track(
        self,
        prefix: str = "",
        serial: str = "",
        tracking_number: str = "",
        language: str = "en-us",
        force_refresh: bool = False,
        **kwargs,
    ) -> ProviderResult:
        if not prefix or not serial:
            if tracking_number and "-" in tracking_number:
                prefix, serial = tracking_number.split("-", 1)
            elif tracking_number and len(tracking_number) >= 11:
                prefix, serial = tracking_number[:3], tracking_number[3:]

        start_time = time.time()
        curl_cmd = None
        response_text = None
        curl_parts: List[str] = []

        if prefix and prefix != "176":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by Emirates SkyCargo (expects 176)",
                latency_ms=latency,
                request_curl=curl_cmd,
                response_body=response_text,
            )

        try:
            logger.info(f"Emirates SkyCargo: Tracking {prefix}-{serial}...")
            token = await self._get_access_token(force_refresh=force_refresh)
            if not token:
                latency = round((time.time() - start_time) * 1000, 2)
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=401,
                    error="Emirates SkyCargo: Unable to obtain guest authentication token.",
                    latency_ms=latency,
                    request_curl=curl_cmd,
                    response_body=response_text,
                )

            headers = {
                **BASE_HEADERS,
                "authorization": f"Bearer {token}",
            }

            awb_full = f"{prefix}{serial}"
            search_payload = {
                "orderFilter": {
                    "airCapacity": {
                        "documentNumbers": [awb_full],
                        "includeItinerary": False,
                    }
                },
                "pageRequest": {
                    "page": 1,
                    "pageSize": 10,
                },
            }

            curl_parts.append(self.build_curl_command("POST", SEARCH_URL, headers=headers, body=search_payload))
            curl_cmd = "\n\n".join(curl_parts)

            async with httpx.AsyncClient(timeout=30.0, verify=False, follow_redirects=True) as client:
                resp = await client.post(SEARCH_URL, json=search_payload, headers=headers)
                response_text = resp.text

                # If 401 Unauthorized, refresh token once and retry
                if resp.status_code == 401 and not force_refresh:
                    logger.info("Emirates SkyCargo: 401 received, refreshing token...")
                    token = await self._get_access_token(force_refresh=True)
                    headers["authorization"] = f"Bearer {token}"
                    resp = await client.post(SEARCH_URL, json=search_payload, headers=headers)
                    response_text = resp.text

                if resp.status_code != 200:
                    latency = round((time.time() - start_time) * 1000, 2)
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=resp.status_code,
                        error=f"Emirates SkyCargo HTTP {resp.status_code}",
                        latency_ms=latency,
                        request_curl=curl_cmd,
                        response_body=response_text,
                    )

                search_data = resp.json()
                orders = (search_data.get("data") or {}).get("order", [])
                if not orders:
                    latency = round((time.time() - start_time) * 1000, 2)
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error=f"No tracking data found for AWB {prefix}-{serial} on Emirates SkyCargo.",
                        latency_ms=latency,
                        request_curl=curl_cmd,
                        response_body=response_text,
                    )

                order = orders[0]
                order_items = (order.get("orderItems") or {}).get("orderItem", [])
                if not order_items:
                    latency = round((time.time() - start_time) * 1000, 2)
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error=f"No order items found for AWB {prefix}-{serial} on Emirates SkyCargo.",
                        latency_ms=latency,
                        request_curl=curl_cmd,
                        response_body=response_text,
                    )

                primary_item = order_items[0]
                booking_ref = (primary_item.get("reference") or {}).get("bookingReferenceNumber")

                # Step 2: Fetch detailed order with full milestones history if available
                final_item = primary_item
                if booking_ref:
                    detail_url = f"{ORDER_URL_BASE}{booking_ref}"
                    curl_parts.append(self.build_curl_command("GET", detail_url, headers=headers))
                    curl_cmd = "\n\n".join(curl_parts)

                    try:
                        resp2 = await client.get(detail_url, headers=headers)
                        if resp2.status_code == 200:
                            response_text = f"--- SUMMARY ---\n{resp.text}\n\n--- DETAIL ---\n{resp2.text}"
                            detail_data = resp2.json()
                            detail_items = ((detail_data.get("data") or {}).get("orderItems") or {}).get("orderItem", [])
                            if detail_items:
                                final_item = detail_items[0]
                    except Exception as e:
                        logger.warning(f"Emirates SkyCargo: Failed to fetch detail milestones: {e}")

                latency = round((time.time() - start_time) * 1000, 2)
                result = self._parse_item(final_item, prefix, serial, latency, booking_ref)
                result.request_curl = curl_cmd
                result.response_body = response_text
                return result

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Emirates SkyCargo tracking request timed out.",
                latency_ms=latency,
                request_curl=curl_cmd,
                response_body=response_text,
            )
        except httpx.HTTPStatusError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            resp_body = exc.response.text if hasattr(exc, "response") else response_text
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code if hasattr(exc, "response") else 500,
                error=str(exc),
                latency_ms=latency,
                request_curl=curl_cmd,
                response_body=resp_body,
            )
        except Exception as exc:
            logger.error(f"Emirates SkyCargo tracking error: {exc}", exc_info=True)
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
                request_curl=curl_cmd,
                response_body=response_text,
            )

    def _parse_item(
        self,
        item: Dict[str, Any],
        prefix: str,
        serial: str,
        latency: float,
        booking_ref: Optional[str] = None,
    ) -> ProviderResult:
        """Parse Emirates SkyCargo orderItem into normalized ProviderResult."""
        air_cap = (item.get("productInfo") or {}).get("airCapacity", {})

        origin_info = air_cap.get("origin") or {}
        dest_info = air_cap.get("destination") or {}
        origin = origin_info.get("code")
        destination = dest_info.get("code")

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

        fulfillment = item.get("fulfillmentInfo") or {}
        service_info = fulfillment.get("serviceInfo") or {}
        milestones = service_info.get("milestone") or []

        events: List[Dict[str, Any]] = []
        for ms in milestones:
            code_info = ms.get("code") or {}
            status_code = code_info.get("code", "")
            description = ms.get("importStatusMessage") or code_info.get("description", status_code)

            station_info = ms.get("station") or {}
            station = station_info.get("code", "")

            status_date = ms.get("statusDate") or {}
            achieved = status_date.get("achieved")
            event_time = self._parse_datetime(achieved)

            status_data = ms.get("statusData") or {}
            qty = status_data.get("quantity") or {}
            event_pieces = qty.get("piece") or pieces
            event_weight = (qty.get("weight") or {}).get("value") or weight_val

            itin = status_data.get("itinerary") or {}
            transport = itin.get("transportInfo") or {}
            flight_info = None
            if transport.get("carrier") and transport.get("number"):
                flight_info = f"{transport['carrier']}-{transport['number']}"

            events.append({
                "station": station,
                "status_code": status_code,
                "status_message": description,
                "event_time": event_time,
                "flight_info": flight_info,
                "flight_number": flight_info,
                "pieces": event_pieces,
                "weight": event_weight,
                "raw_status": status_code,
                "is_latest": ms.get("latestMilestone", False),
            })

        # Sort events chronologically (oldest to newest)
        events.sort(key=lambda x: x.get("event_time") or "")

        # Find latest event: marked with latestMilestone or last in sorted list
        latest_event = None
        for ev in reversed(events):
            if ev.get("is_latest"):
                latest_event = ev
                break
        if not latest_event and events:
            latest_event = events[-1]

        overall_status = "In Transit"
        if latest_event:
            st_code = latest_event.get("status_code", "")
            overall_status = _STATUS_MAP.get(st_code, latest_event.get("status_message", "In Transit"))

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=overall_status,
            origin=origin,
            destination=destination,
            pieces=pieces,
            weight={"value": weight_val, "unit": "kg"} if weight_val is not None else None,
            volume=volume_val,
            events=events,
            latest_event=latest_event,
            raw_data={
                "carrier": "Emirates SkyCargo",
                "awb": f"{prefix}-{serial}",
                "origin_name": origin_info.get("name"),
                "destination_name": dest_info.get("name"),
                "booking_reference": booking_ref,
                "commodity": cargo_info.get("goodsDescription"),
                "commodity_code": (cargo_info.get("commodityCode") or {}).get("code"),
                "product": ((air_cap.get("product") or {}).get("product") or {}).get("description"),
            },
            latency_ms=latency,
        )

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[str]:
        if not dt_str:
            return None
        dt_clean = str(dt_str).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(dt_clean, fmt).isoformat()
            except ValueError:
                continue
        return dt_clean
