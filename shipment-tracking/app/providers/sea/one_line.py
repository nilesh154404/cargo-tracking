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
ONE_API_COP_EVENTS_URL = "https://ecomm.one-line.com/api/v2/edh/containers/track-and-trace/cop-events"

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
                        # Success! Now fetch detailed COP events for each container
                        cop_events_by_container: Dict[str, List[Dict[str, Any]]] = {}
                        last_cop_curl: Optional[str] = None

                        async with httpx.AsyncClient(timeout=15.0) as cop_client:
                            for c in containers_data:
                                c_no = c.get("containerNo")
                                b_no = c.get("bookingNo")
                                if c_no and b_no:
                                    try:
                                        cop_corr_id = str(uuid.uuid4())
                                        cop_headers = {**ONE_HEADERS, "x-correlation-id": cop_corr_id}
                                        cop_params = {"booking_no": b_no, "container_no": c_no}
                                        cop_full_url = f"{ONE_API_COP_EVENTS_URL}?booking_no={b_no}&container_no={c_no}"
                                        last_cop_curl = self.build_curl_command(
                                            method="GET",
                                            url=cop_full_url,
                                            headers=cop_headers,
                                        )
                                        cop_resp = await cop_client.get(
                                            ONE_API_COP_EVENTS_URL,
                                            params=cop_params,
                                            headers=cop_headers,
                                        )
                                        if cop_resp.status_code in (200, 201):
                                            cop_data = cop_resp.json().get("data") or []
                                            cop_events_by_container[c_no] = cop_data
                                    except Exception as cop_exc:
                                        logger.warning(f"Error fetching ONE Line COP events for {c_no} / {b_no}: {cop_exc}")

                        latency_ms = round((time.time() - start_time) * 1000, 2)
                        return self._parse_tracking_response(
                            containers_data=containers_data,
                            cop_events_by_container=cop_events_by_container,
                            search_text=search_text,
                            search_type=search_type,
                            raw_target=raw_target,
                            search_curl=curl_cmd,
                            cop_curl=last_cop_curl,
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
        search_curl: Optional[str] = None,
        cop_curl: Optional[str] = None,
        cop_events_by_container: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        curl_cmd: Optional[str] = None,
        resp_text: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> ProviderResult:
        """
        Parses ONE Line response containing one or more containers (e.g. multi-container booking).
        Aggregates events (preferring detailed COP events), coordinates, and container breakdown.
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
        cop_map = cop_events_by_container or {}

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
            if latest_ev_name:
                latest_status_message = latest_ev_name

            c_cop_events = cop_map.get(c_no) or []
            if c_cop_events:
                # 1. Parse rich COP events from /cop-events endpoint
                for ev in c_cop_events:
                    ev_name = ev.get("eventName") or "Milestone"
                    date_iso = ev.get("eventDate") or ev.get("eventLocalPortDate")
                    matrix_id = ev.get("matrixId") or ev.get("opusCode") or "EVENT"
                    trigger = ev.get("triggerType") or "ACTUAL"

                    loc = ev.get("location") or {}
                    loc_name = loc.get("locationName") or ev.get("nodeCode")
                    country_name = loc.get("countryName")
                    station_str = loc_name
                    if country_name and country_name not in (station_str or ""):
                        station_str = f"{station_str}, {country_name}" if station_str else country_name

                    yard = ev.get("yard") or {}
                    yard_name = yard.get("yardName")
                    if yard_name:
                        station_str = f"{station_str} ({yard_name})" if station_str else yard_name

                    # Coordinate lookup
                    coords = match_location(loc.get("locationName") or station_str, "SEA")

                    ev_vessel = ev.get("vessel") or ev.get("edhVessel") or {}
                    v_name = ev_vessel.get("name") or c_vessel
                    v_voy = ev_vessel.get("voyNo") or c_voyage
                    flight_info_str = f"{c_no}"
                    if v_name:
                        flight_info_str += f" | {v_name}"
                        if v_voy:
                            flight_info_str += f" (Voyage {v_voy})"

                    ev_dict = {
                        "station": station_str,
                        "status_code": matrix_id,
                        "status_message": f"[{c_no}] {ev_name}" if len(containers_data) > 1 else ev_name,
                        "event_time": date_iso,
                        "flight_info": flight_info_str,
                        "pieces": 1,
                        "weight": w_val,
                        "raw_status": trigger,
                        "coordinates": coords,
                    }
                    all_events.append(ev_dict)

                # Determine latest status from the last ACTUAL milestone
                actual_events = [ev for ev in c_cop_events if ev.get("triggerType") == "ACTUAL"]
                if actual_events:
                    latest_status_message = actual_events[-1].get("eventName") or latest_status_message

                # Enrich origin and destination if missing
                if not origin and c_cop_events:
                    first_loc = (c_cop_events[0].get("location") or {}).get("locationName")
                    if first_loc:
                        origin = first_loc
                if not destination and c_cop_events:
                    last_loc = (c_cop_events[-1].get("location") or {}).get("locationName")
                    if last_loc:
                        destination = last_loc
            else:
                # 2. Fallback to cargoEvents from container search
                cargo_events = c.get("cargoEvents") or []
                for ev in cargo_events:
                    matrix_id = ev.get("matrixId")
                    loc_name = ev.get("locationName")
                    country_name = ev.get("countryName")
                    date_iso = ev.get("localPortDate") or ev.get("date")
                    trigger = ev.get("trigger") or "ACTUAL"

                    status_name = ONE_MATRIX_EVENT_NAMES.get(
                        matrix_id,
                        latest_ev_name if matrix_id == latest_ev.get("matrixId") else f"Milestone ({matrix_id})",
                    )

                    station_str = loc_name
                    if country_name and country_name not in (station_str or ""):
                        station_str = f"{station_str}, {country_name}" if station_str else country_name

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
                "origin": c_origin or origin,
                "destination": c_dest or destination,
                "status": latest_status_message,
                "latest_event": latest_ev,
                "cop_events_count": len(c_cop_events),
                "events_count": len(c_cop_events) if c_cop_events else len(c.get("cargoEvents") or []),
            })

        # Set latest overall event
        if containers_data:
            c0 = containers_data[0]
            c0_no = c0.get("containerNo") or raw_target
            c0_cop = cop_map.get(c0_no) or []
            if c0_cop:
                actuals = [ev for ev in c0_cop if ev.get("triggerType") == "ACTUAL"]
                le_cop = actuals[-1] if actuals else c0_cop[-1]
                loc = le_cop.get("location") or {}
                le_loc = loc.get("locationName") or le_cop.get("nodeCode")
                coords = match_location(le_loc, "SEA") if le_loc else None
                le_vessel = le_cop.get("vessel") or le_cop.get("edhVessel") or {}
                v_name = le_vessel.get("name") or vessel_name
                latest_event_overall = {
                    "station": le_loc,
                    "status_code": le_cop.get("matrixId") or le_cop.get("opusCode") or "LATEST",
                    "status_message": le_cop.get("eventName") or latest_status_message,
                    "event_time": le_cop.get("eventDate") or le_cop.get("eventLocalPortDate"),
                    "flight_info": f"{c0_no} | {v_name or ''}".strip(" |"),
                    "coordinates": coords,
                }
            else:
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

        effective_curl = search_curl or curl_cmd
        if cop_curl:
            effective_curl = f"{effective_curl}\n\n# --- Step 2: ONE Line Detailed COP Events API ---\n{cop_curl}"

        raw_data_summary = {
            "search_text": search_text,
            "search_type_used": search_type,
            "total_containers": len(containers_data),
            "containers": containers_summary,
            "vessel_name": vessel_name,
            "voyage_no": voyage_no,
            "search_curl": search_curl or curl_cmd,
            "cop_events_curl": cop_curl,
            "cop_events": cop_map,
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
            request_curl=effective_curl,
            response_body=resp_text,
            latency_ms=latency_ms,
        )
