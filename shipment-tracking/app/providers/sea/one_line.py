import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult
from app.services.location_matcher import match_location

logger = logging.getLogger("shipment_tracking.providers.one_line")

ONE_API_SEARCH_URL = "https://ecomm.one-line.com/api/v2/edh/containers/track-and-trace/search"

ONE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-IN,en-US;q=0.9,en;q=0.8",
    "cache-control": "no-cache, no-store, must-revalidate",
    "content-type": "application/json",
    "origin": "https://www.one-line.com",
    "referer": "https://www.one-line.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Google Chrome";v="120", "Chromium";v="120", "Not(A:Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}

# Standard milestone / matrix event names for Ocean Network Express
ONE_MATRIX_EVENT_NAMES = {
    "E010": "Empty Equipment Dispatched",
    "E020": "Empty Equipment Received by Shipper",
    "E030": "Gate In at Origin Terminal / Inland Depo",
    "E040": "Cargo Loaded on Feeder / Rail",
    "E050": "Container Gate In at Port of Loading",
    "E060": "Container Loaded on Vessel",
    "E061": "Vessel Departure from Port of Loading",
    "E070": "Vessel In Transit",
    "E080": "Vessel Arrival at Transshipment Port",
    "E085": "Container Discharged at Transshipment Port",
    "E089": "Vessel Arrival at Port of Discharge",
    "E105": "Container Discharged from Vessel",
    "E110": "Customs Cleared / Available for Pickup",
    "E120": "Container Gate Out from Port of Discharge",
    "E130": "Container Delivered to Consignee",
    "E138": "Empty Container Returned from Customer",
    "E167": "Documentation Cut-off / Cargo Received",
}


def _parse_weight_string(weight_str: Optional[str]) -> tuple[Optional[float], str]:
    """Parse '7,870.000 KGS' or '10,920.000 LBS' into numeric and unit."""
    if not weight_str:
        return None, "kg"
    cleaned = str(weight_str).replace(",", "").strip()
    match = re.search(r"([\d\.]+)\s*([A-Za-z]+)?", cleaned)
    if match:
        val = float(match.group(1))
        unit = (match.group(2) or "kg").lower()
        if unit.startswith("kg"):
            unit = "kg"
        elif unit.startswith("lb"):
            unit = "lbs"
        return val, unit
    return None, "kg"


class OneLineProvider(BaseProvider):
    """
    Direct Live Provider for Ocean Network Express (ONE).
    Supports all 3 search types:
      - CNTR_NO: Container number (e.g. ONEU2157736, ONEU1728682)
      - BKG_NO: Booking / Ocean B/L number (e.g. BLRG06172700, ONEYBLRG06172700)
                Returns all containers associated with the booking!
      - PO_NO: Purchase Order number
    """

    name = "one_line"
    mode = "SEA"

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
        **kwargs,
    ) -> ProviderResult:
        start_time = time.time()
        raw_target = (tracking_number or f"{prefix}{serial}").strip()
        search_type_override = kwargs.get("search_type")

        # Determine candidate search queries & search types
        # Check if booking / OBL number or container number passed in kwargs
        mawb_obl_no = kwargs.get("mawb_obl_no")
        container_no = kwargs.get("container_no")

        attempts_plan: List[tuple[str, str]] = []
        if search_type_override in ("CNTR_NO", "BKG_NO", "PO_NO"):
            target = container_no if (search_type_override == "CNTR_NO" and container_no) else (mawb_obl_no or raw_target)
            attempts_plan.append((target, search_type_override))
        else:
            # Container search candidate
            is_container_format = bool(re.match(r"^[A-Z]{4}\d{7}$", raw_target)) or raw_target.startswith("ONEU")
            is_booking_format = raw_target.startswith("ONEY") or bool(re.match(r"^[A-Z]{4}\d{8,}$", raw_target))

            if container_no and bool(re.match(r"^[A-Z]{4}\d{7}$", container_no)):
                attempts_plan.append((container_no, "CNTR_NO"))
            if mawb_obl_no:
                attempts_plan.append((mawb_obl_no, "BKG_NO"))

            if is_booking_format:
                attempts_plan.append((raw_target, "BKG_NO"))
                attempts_plan.append((raw_target, "CNTR_NO"))
            elif is_container_format:
                attempts_plan.append((raw_target, "CNTR_NO"))
                attempts_plan.append((raw_target, "BKG_NO"))
            else:
                attempts_plan.append((raw_target, "CNTR_NO"))
                attempts_plan.append((raw_target, "BKG_NO"))
                attempts_plan.append((raw_target, "PO_NO"))

        last_resp = None
        last_curl = None
        last_error = None

        # Execute searches sequentially until one returns container data
        for search_text, search_type in attempts_plan:
            corr_id = str(uuid.uuid4())
            req_headers = {**ONE_HEADERS, "x-correlation-id": corr_id}
            payload = {
                "page": 1,
                "page_length": 10,
                "filters": {
                    "search_text": search_text,
                    "search_type": search_type,
                },
                "timestamp": int(time.time() * 1000),
            }

            curl_cmd = self.build_curl_command(
                method="POST",
                url=ONE_API_SEARCH_URL,
                headers=req_headers,
                body=payload,
            )
            last_curl = curl_cmd

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        ONE_API_SEARCH_URL,
                        headers=req_headers,
                        json=payload,
                    )
                latency_ms = round((time.time() - start_time) * 1000, 2)
                last_resp = resp

                if resp.status_code in (200, 201):
                    data_json = resp.json()
                    containers_data = data_json.get("data") or []
                    if containers_data:
                        # Success! Parse container(s) tracking data
                        return self._parse_tracking_response(
                            containers_data=containers_data,
                            search_text=search_text,
                            search_type=search_type,
                            raw_target=raw_target,
                            curl_cmd=curl_cmd,
                            resp_text=resp.text,
                            latency_ms=latency_ms,
                        )
                elif resp.status_code == 400:
                    last_error = f"ONE Line returned 400 Bad Request for search_type '{search_type}'."
                else:
                    last_error = f"ONE Line returned HTTP {resp.status_code}."
            except Exception as exc:
                logger.warning(f"Error querying ONE Line API ({search_type}): {exc}")
                last_error = str(exc)

        latency_ms = round((time.time() - start_time) * 1000, 2)
        return ProviderResult(
            success=False,
            provider_name=self.name,
            status_code=last_resp.status_code if last_resp else 500,
            status="NOT_FOUND",
            error=last_error or f"No tracking records found for '{raw_target}' on Ocean Network Express (ONE).",
            request_curl=last_curl,
            response_body=last_resp.text if last_resp else None,
            latency_ms=latency_ms,
        )

    def _parse_tracking_response(
        self,
        containers_data: List[Dict[str, Any]],
        search_text: str,
        search_type: str,
        raw_target: str,
        curl_cmd: str,
        resp_text: str,
        latency_ms: float,
    ) -> ProviderResult:
        """
        Parses ONE Line response containing one or more containers (e.g. multi-container booking).
        Aggregates events, coordinates, and container breakdown.
        """
        all_events: List[Dict[str, Any]] = []
        containers_summary: List[Dict[str, Any]] = []
        total_weight_kg = 0.0
        vessel_name = None
        voyage_no = None
        origin = None
        destination = None
        latest_status_message = "IN_TRANSIT"
        latest_event_overall: Optional[Dict[str, Any]] = None

        for c in containers_data:
            c_no = c.get("containerNo") or raw_target
            b_no = c.get("bookingNo")
            c_type = c.get("containerTypeSize")
            w_str = c.get("weight")
            w_val, _ = _parse_weight_string(w_str)
            if w_val:
                total_weight_kg += w_val

            vessel_info = c.get("vesselVoyage") or {}
            c_vessel = vessel_info.get("vesselName")
            c_voyage = vessel_info.get("voyageNo")
            if not vessel_name and c_vessel:
                vessel_name = c_vessel
                voyage_no = c_voyage

            por = c.get("por") or {}
            pod = c.get("pod") or {}
            c_origin = por.get("locationName") or por.get("code")
            c_dest = pod.get("locationName") or pod.get("code")
            if not origin and c_origin:
                origin = c_origin
            if not destination and c_dest:
                destination = c_dest

            latest_ev = c.get("latestEvent") or {}
            latest_ev_name = latest_ev.get("eventName")
            latest_ev_date = latest_ev.get("date")
            latest_ev_loc = latest_ev.get("locationName")
            if latest_ev_name:
                latest_status_message = latest_ev_name

            cargo_events = c.get("cargoEvents") or []
            for ev in cargo_events:
                matrix_id = ev.get("matrixId")
                loc_name = ev.get("locationName")
                country_name = ev.get("countryName")
                country_code = ev.get("countryCode")
                date_iso = ev.get("localPortDate") or ev.get("date")
                trigger = ev.get("trigger") or "ACTUAL"

                status_name = ONE_MATRIX_EVENT_NAMES.get(
                    matrix_id,
                    latest_ev_name if matrix_id == latest_ev.get("matrixId") else f"Milestone ({matrix_id})",
                )

                station_str = loc_name
                if country_name and country_name not in (station_str or ""):
                    station_str = f"{station_str}, {country_name}" if station_str else country_name

                # Match coordinates with seaport location dataset
                coords = match_location(loc_name or station_str, "SEA")

                flight_info_str = f"{c_no}"
                if c_vessel:
                    flight_info_str += f" | {c_vessel}"
                    if c_voyage:
                        flight_info_str += f" (Voyage {c_voyage})"

                ev_dict = {
                    "station": station_str,
                    "status_code": matrix_id or "EVENT",
                    "status_message": f"[{c_no}] {status_name}" if len(containers_data) > 1 else status_name,
                    "event_time": date_iso,
                    "flight_info": flight_info_str,
                    "pieces": 1,
                    "weight": w_val,
                    "raw_status": trigger,
                    "coordinates": coords,
                }
                all_events.append(ev_dict)

            containers_summary.append({
                "container_number": c_no,
                "booking_number": b_no,
                "container_type": c_type,
                "weight": w_str,
                "weight_kg": w_val,
                "vessel_name": c_vessel,
                "voyage_no": c_voyage,
                "origin": c_origin,
                "destination": c_dest,
                "status": latest_ev_name or "In Transit",
                "latest_event": latest_ev,
                "events_count": len(cargo_events),
            })

        # Set latest overall event
        if containers_data:
            c0 = containers_data[0]
            le = c0.get("latestEvent") or {}
            le_loc = le.get("locationName")
            coords = match_location(le_loc, "SEA") if le_loc else None
            latest_event_overall = {
                "station": le_loc,
                "status_code": le.get("matrixId") or "LATEST",
                "status_message": le.get("eventName") or latest_status_message,
                "event_time": le.get("date"),
                "flight_info": f"{c0.get('containerNo')} | {vessel_name or ''}".strip(" |"),
                "coordinates": coords,
            }

        weight_dict = None
        if total_weight_kg > 0:
            weight_dict = {"value": round(total_weight_kg, 2), "unit": "kg"}

        raw_data_summary = {
            "search_text": search_text,
            "search_type_used": search_type,
            "total_containers": len(containers_data),
            "containers": containers_summary,
            "vessel_name": vessel_name,
            "voyage_no": voyage_no,
        }

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=latest_status_message,
            origin=origin,
            destination=destination,
            pieces=len(containers_data),
            weight=weight_dict,
            volume=None,
            events=all_events,
            latest_event=latest_event_overall,
            raw_data=raw_data_summary,
            request_curl=curl_cmd,
            response_body=resp_text,
            latency_ms=latency_ms,
        )
