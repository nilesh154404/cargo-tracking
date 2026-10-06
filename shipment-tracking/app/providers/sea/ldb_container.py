import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.ldb_container")

LDB_SEARCH_URL = "https://ldb.co.in/api/ldb/container/search"

LDB_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://ldb.co.in/ldb/containersearch/39",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

EVENT_CODE_MAP = {
    "PORT OUT": "PRT_OUT",
    "PORT IN": "PRT_IN",
    "VESSEL DEPARTED": "DEP",
    "VESSEL ARRIVED": "ARR",
    "ETD": "ETD",
    "ETA": "ETA",
    "GATE CUT OFF": "GCO",
    "TERMINAL IN": "TRM_IN",
    "GATE IN": "GT_IN",
    "GATE OUT": "GT_OUT",
    "GATE CROSSED": "GT_CRS",
    "TOLL PLAZA CROSSED": "TOLL_CRS",
    "CFS IN": "CFS_IN",
    "CFS OUT": "CFS_OUT",
    "DPE": "DPE",
    "LOADED": "LOAD",
    "DISCHARGED": "DISCH",
    "DELIVERED": "DLV",
    "EMPTY RECEIVED": "MT_RET",
}


def _resolve_status_code(event_name: str) -> str:
    name_upper = (event_name or "").upper()
    for key, code in EVENT_CODE_MAP.items():
        if key in name_upper:
            return code
    return "INFO"


class LdbContainerProvider(BaseProvider):
    """
    Logistics Data Bank (NICDC LDB) live container tracking provider.
    Provides container tracking across ports, CFS, ICDs, and toll plazas in India,
    including Ocean Network Express (ONE) and multi-modal moves.
    """

    name = "ldb_container"
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

        params = {
            "cntrNo": container_id,
            "searchType": "39",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    LDB_SEARCH_URL,
                    params=params,
                    headers=LDB_HEADERS,
                )

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"LDB API returned HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            data = resp.json()
            msg_text = data.get("message", {}).get("text", "")
            obj = data.get("object")

            if not obj or msg_text == "No Record Found":
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"No shipment tracking records found for container {container_id} on Logistics Data Bank (LDB)",
                    latency_ms=latency,
                    raw_data=data,
                )

            # 1. Container Details
            cntr_detail = obj.get("cntrDetail") or {}
            container_type = cntr_detail.get("containerType") or cntr_detail.get("size") or "Container"
            iso_code = cntr_detail.get("isoCode")

            # 2. Extract Vessel Name if available
            vessel_name = None
            v_exp = obj.get("vesselStatusExportDpt") or {}
            v_cut = obj.get("vesselStatusGateCutOff") or {}
            v_imp = obj.get("vesselStatusImportDpt") or {}
            v_etd = obj.get("vesselStatusEtdOfEta") or {}

            for v_source in [v_exp, v_cut, v_imp, v_etd]:
                if v_source.get("vesselname"):
                    vessel_name = v_source.get("vesselname").strip()
                    break

            # 3. Parse and sort milestones chronologically
            raw_events = obj.get("trackingInfoSearchDownload") or obj.get("trackLog") or []
            sorted_raw = sorted(
                raw_events,
                key=lambda x: (x.get("timeInMs") or 0, x.get("timestampTimezone") or ""),
            )

            parsed_events: List[Dict[str, Any]] = []
            for ev in sorted_raw:
                event_name = ev.get("eventName") or "Status Update"
                loc = ev.get("currentLocation")
                superorg = ev.get("superorg")
                transport_mode = ev.get("transportmode") or ""
                time_iso = ev.get("timestampTimezone")
                is_empty_val = ev.get("isEmpty")

                # If vessel name was not in top-level status, check event attributes
                if not vessel_name and is_empty_val and is_empty_val not in ("N", "Y"):
                    vessel_name = is_empty_val.strip()

                # Build readable station name
                station_parts = []
                if loc:
                    station_parts.append(loc)
                if superorg and (not loc or superorg.lower() not in loc.lower()):
                    station_parts.append(superorg)
                station_str = " | ".join(station_parts) if station_parts else (superorg or "Port / Terminal")

                # Build readable status message
                msg_parts = [event_name]
                if transport_mode:
                    msg_parts.append(f"Mode: {transport_mode}")
                if vessel_name and (transport_mode == "VESSEL" or "VESSEL" in event_name.upper()):
                    msg_parts.append(f"Vessel: {vessel_name}")

                parsed_events.append({
                    "station": station_str,
                    "status_code": _resolve_status_code(event_name),
                    "status_message": " - ".join(msg_parts),
                    "event_time": time_iso,
                    "flight_info": f"Vessel: {vessel_name}" if (vessel_name and (transport_mode == "VESSEL" or "VESSEL" in event_name.upper())) else None,
                    "pieces": 1,
                    "weight": 28000.0,
                    "raw_status": event_name,
                })

            if not parsed_events:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"No milestone events found for container {container_id}",
                    latency_ms=latency,
                    raw_data=data,
                )

            # Determine origin: first event with a real port/station name (skipping generic 'Port / Terminal')
            origin = None
            for ev in parsed_events:
                st = ev.get("station")
                if st and st != "Port / Terminal":
                    origin = st
                    break
            if not origin and parsed_events:
                origin = parsed_events[0]["station"]

            destination = parsed_events[-1]["station"] if parsed_events else None

            latest_event = parsed_events[-1]
            last_name = (latest_event.get("raw_status") or "").upper()
            last_code = latest_event.get("status_code")

            if last_code in ("DLV", "MT_RET") or "DELIVER" in last_name:
                overall_status = "Delivered"
            elif "PORT OUT" in last_name or "VESSEL" in last_name or last_code in ("DEP", "PRT_OUT"):
                overall_status = "In Transit"
            elif "GATE IN" in last_name or "TERMINAL IN" in last_name or "PORT IN" in last_name:
                overall_status = "In Terminal"
            else:
                overall_status = "In Transit"

            # Determine dynamic carrier branding
            prefix_upper = prefix.upper()
            if prefix_upper in ("ONEU", "ONEY"):
                carrier_label = "Ocean Network Express (ONE) / LDB"
            elif prefix_upper in ("MRSU", "MAEU", "MSKU", "APMU", "MNBU") or (vessel_name and "MAERSK" in vessel_name.upper()):
                carrier_label = "Maersk Line / LDB"
            elif prefix_upper in ("MSCU", "MSMU", "MEDU"):
                carrier_label = "MSC / LDB"
            else:
                carrier_label = f"Shipping Line ({prefix_upper}) / LDB"

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=overall_status,
                origin=origin,
                destination=destination,
                pieces=1,
                weight={"unit": "kg", "value": 28000.0},
                volume=76.2 if "40" in container_type else 33.2,
                events=parsed_events,
                latest_event=latest_event,
                raw_data={
                    "carrier": carrier_label,
                    "container_number": container_id,
                    "container_type": container_type,
                    "iso_code": iso_code,
                    "vessel_name": vessel_name,
                    "events_count": len(parsed_events),
                    "source": "Logistics Data Bank (ldb.co.in)",
                },
                latency_ms=latency,
            )

        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to LDB API: {str(exc)}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Unexpected error parsing LDB response: {str(exc)}",
                latency_ms=latency,
            )
