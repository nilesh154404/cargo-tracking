import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.agents.routing_agent import RoutingAgent
from app.tools.air_tracking_tools import AirTrackingTool
from app.tools.sea_tracking_tools import SeaTrackingTool
from app.tools.db_tools import DatabasePersistenceTool
from app.schemas.tracking import (
    AgentDecisionTrail,
    CarrierInfo,
    LocationCoordinates,
    ProviderAttempt,
    UnifiedTrackingEvent,
    UnifiedTrackingResponse,
    sort_events_descending,
)
from app.services.location_matcher import match_location

logger = logging.getLogger("shipment_tracking.agents.orchestrator")


class TrackingOrchestratorAgent:
    """
    Master Agentic Orchestrator for Air and Sea shipment tracking.
    Enforces 100% Real Live tracking data without mock data.
    Provides clear, relatable error messages for:
    - Invalid tracking numbers
    - Unsupported airlines / prefixes
    - Unsupported shipping lines / sea prefixes
    - Tracking not found / no records
    """

    def __init__(self):
        self.routing_agent = RoutingAgent()
        self.air_tool = AirTrackingTool
        self.sea_tool = SeaTrackingTool
        self.db_tool = DatabasePersistenceTool

    async def execute_tracking(
        self,
        query: Optional[str] = None,
        db: Optional[Session] = None,
        explicit_mode: Optional[str] = None,
        force_refresh: bool = False,
        tenant_id: Optional[int] = None,
        customer_reference: Optional[str] = None,
        mawb_obl_no: Optional[str] = None,
        container_no: Optional[str] = None,
        carrier_code: Optional[str] = None,
        carrier_name: Optional[str] = None,
        vessel_name: Optional[str] = None,
        hawb_hbl_no: Optional[str] = None,
        flight_no: Optional[str] = None,
        search_type: Optional[str] = None,
    ) -> UnifiedTrackingResponse:
        # Resolve active tracking query from container_no, mawb_obl_no, or query
        active_query = (
            container_no
            or mawb_obl_no
            or query
            or ""
        ).strip()
        if not active_query:
            active_query = "UNKNOWN"

        # Step 1: Database-driven carrier & format identification
        route_plan = self.routing_agent.route(
            query=active_query,
            explicit_mode=explicit_mode,
            db=db,
            carrier_code_override=carrier_code,
        )

        # Case 1: Invalid Tracking Number Format
        if not route_plan.is_valid_format:
            logger.info(f"Invalid tracking format for query '{query}': {route_plan.relatable_message}")
            return UnifiedTrackingResponse(
                tracking_number=route_plan.clean_tracking_number,
                mode=route_plan.mode,
                carrier=CarrierInfo(
                    code=route_plan.carrier_code,
                    prefix=route_plan.prefix,
                    name=route_plan.carrier_name,
                    mode=route_plan.mode,
                    primary_provider="none",
                    fallback_providers=[],
                ),
                status="INVALID_TRACKING_NUMBER",
                message=route_plan.relatable_message,
                latest_event=None,
                events=[],
                agent_trail=AgentDecisionTrail(
                    detected_mode=route_plan.mode,
                    carrier_identified=route_plan.carrier_name,
                    carrier_code=route_plan.carrier_code,
                    provider_plan=[],
                    attempts=[],
                    final_provider_used=None,
                ),
                raw_data=None,
            )

        # Case 2: Carrier / Prefix Not Supported for Live Tracking
        if not route_plan.is_supported:
            logger.info(f"Carrier not supported for query '{query}': {route_plan.relatable_message}")
            unsupported_status = (
                "AIRLINE_NOT_SUPPORTED" if route_plan.mode == "AIR" else "SHIPPING_LINE_NOT_SUPPORTED"
            )
            return UnifiedTrackingResponse(
                tracking_number=route_plan.clean_tracking_number,
                mode=route_plan.mode,
                carrier=CarrierInfo(
                    code=route_plan.carrier_code,
                    prefix=route_plan.prefix,
                    name=route_plan.carrier_name,
                    mode=route_plan.mode,
                    primary_provider=route_plan.primary_provider,
                    fallback_providers=route_plan.fallback_providers,
                ),
                status=unsupported_status,
                message=route_plan.relatable_message,
                latest_event=None,
                events=[],
                agent_trail=AgentDecisionTrail(
                    detected_mode=route_plan.mode,
                    carrier_identified=route_plan.carrier_name,
                    carrier_code=route_plan.carrier_code,
                    provider_plan=[route_plan.primary_provider],
                    attempts=[
                        ProviderAttempt(
                            provider_name=route_plan.primary_provider,
                            status="NOT_SUPPORTED",
                            http_status=501,
                            latency_ms=0.0,
                            error=route_plan.relatable_message,
                        )
                    ],
                    final_provider_used=None,
                ),
                raw_data=None,
            )

        providers_to_try = [route_plan.primary_provider]
        for fb in route_plan.fallback_providers:
            if fb and fb not in providers_to_try:
                providers_to_try.append(fb)

        attempts = []
        successful_result = None
        final_provider_used = None
        last_error = None

        logger.info(
            f"Tracking Query: '{query}' | Mode: {route_plan.mode} | "
            f"Carrier: {route_plan.carrier_name} ({route_plan.carrier_code}) | "
            f"Provider Plan: {providers_to_try}"
        )

        # Step 2: Live Provider Execution Loop
        for provider_name in providers_to_try:
            logger.info(f"Attempting live provider: {provider_name}")

            if route_plan.mode == "AIR":
                result = await self.air_tool.execute(
                    provider_name=provider_name,
                    prefix=route_plan.prefix,
                    serial=route_plan.serial_number,
                    tracking_number=route_plan.clean_tracking_number,
                    force_refresh=force_refresh,
                    mawb_obl_no=mawb_obl_no,
                    container_no=container_no,
                    carrier_code=carrier_code,
                    carrier_name=carrier_name,
                    vessel_name=vessel_name,
                    hawb_hbl_no=hawb_hbl_no,
                    flight_no=flight_no,
                    search_type=search_type,
                )
            else:
                result = await self.sea_tool.execute(
                    provider_name=provider_name,
                    prefix=route_plan.prefix,
                    serial=route_plan.serial_number,
                    tracking_number=route_plan.clean_tracking_number,
                    force_refresh=force_refresh,
                    mawb_obl_no=mawb_obl_no,
                    container_no=container_no,
                    carrier_code=carrier_code,
                    carrier_name=carrier_name,
                    vessel_name=vessel_name,
                    hawb_hbl_no=hawb_hbl_no,
                    flight_no=flight_no,
                    search_type=search_type,
                )

            # Check if result was truly successful with valid tracking milestones
            has_milestones = bool(result.events and len(result.events) > 0)
            is_valid_success = result.success and has_milestones and result.status not in ("NOT_FOUND", "EMPTY")

            if is_valid_success:
                logger.info(f"Provider {provider_name} succeeded in {result.latency_ms}ms with status '{result.status}'.")
                attempts.append(
                    ProviderAttempt(
                        provider_name=provider_name,
                        status="SUCCESS",
                        http_status=result.status_code,
                        latency_ms=result.latency_ms,
                        error=None,
                        request_curl=result.request_curl,
                        response_body=result.response_body,
                    )
                )
                successful_result = result
                final_provider_used = provider_name
                break
            else:
                last_error = result.error or f"No tracking records found (HTTP {result.status_code})"
                logger.warning(
                    f"Provider {provider_name} returned no milestones or error: {last_error}."
                )
                attempts.append(
                    ProviderAttempt(
                        provider_name=provider_name,
                        status="NOT_FOUND" if result.status_code == 404 else "FAILED",
                        http_status=result.status_code,
                        latency_ms=result.latency_ms,
                        error=last_error,
                        request_curl=result.request_curl,
                        response_body=result.response_body,
                    )
                )

        # Step 3: Extract normalized milestones if successful
        events_list = []
        latest_event_obj = None

        if successful_result and successful_result.events:
            for ev in successful_result.events:
                coords = ev.get("coordinates")
                if not coords and ev.get("station"):
                    coords = match_location(ev.get("station"), route_plan.mode)

                raw_w = ev.get("weight")
                clean_w = None
                if isinstance(raw_w, (int, float)):
                    clean_w = float(raw_w)
                elif isinstance(raw_w, str):
                    try:
                        clean_w = float(re.sub(r"[^\d.]", "", raw_w.replace(",", "")))
                    except Exception:
                        clean_w = None

                raw_p = ev.get("pieces")
                clean_p = None
                if isinstance(raw_p, int):
                    clean_p = raw_p
                elif isinstance(raw_p, str):
                    try:
                        clean_p = int(re.sub(r"[^\d]", "", raw_p))
                    except Exception:
                        clean_p = None

                event_obj = UnifiedTrackingEvent(
                    station=ev.get("station"),
                    status_code=ev.get("status_code"),
                    status_message=ev.get("status_message", "Status update"),
                    event_time=ev.get("event_time"),
                    flight_info=ev.get("flight_info"),
                    pieces=clean_p,
                    weight=clean_w,
                    raw_status=ev.get("raw_status"),
                    coordinates=LocationCoordinates(**coords) if coords else None,
                )
                events_list.append(event_obj)

            if successful_result.latest_event:
                le = successful_result.latest_event
                le_st = le.get("station")
                le_coords = le.get("coordinates") or (match_location(le_st, route_plan.mode) if le_st else None)
                latest_event_obj = UnifiedTrackingEvent(
                    station=le_st,
                    status_code=le.get("status_code") or le.get("status"),
                    status_message=le.get("status_message") or le.get("statusMsgDisplay") or "Latest event",
                    event_time=le.get("dateTime") or le.get("event_time"),
                    flight_info=le.get("flightInfo") or le.get("flight_info"),
                    pieces=le.get("pieces"),
                    weight=le.get("weight"),
                    coordinates=LocationCoordinates(**le_coords) if le_coords else None,
                )

            # Ensure final response events are ordered descending (latest milestone first)
            events_list = sort_events_descending(events_list)
            if not latest_event_obj and events_list:
                latest_event_obj = events_list[0]

        # Step 4: Persist in MySQL Database
        if db and attempts:
            try:
                if successful_result and successful_result.events:
                    w_val = None
                    w_unit = "kg"
                    if isinstance(successful_result.weight, dict):
                        w_val = successful_result.weight.get("value")
                        w_unit = successful_result.weight.get("unit", "kg")
                    elif isinstance(successful_result.weight, (int, float)):
                        w_val = float(successful_result.weight)

                    self.db_tool.save_snapshot(
                        db=db,
                        tracking_number=route_plan.clean_tracking_number,
                        transport_mode=route_plan.mode,
                        carrier_code=route_plan.carrier_code,
                        carrier_name=route_plan.carrier_name,
                        status=successful_result.status,
                        origin=successful_result.origin,
                        destination=successful_result.destination,
                        pieces=successful_result.pieces,
                        weight_val=w_val,
                        weight_unit=w_unit,
                        volume=successful_result.volume,
                        provider_used=final_provider_used or "none",
                        events=successful_result.events,
                        raw_data=successful_result.raw_data,
                        attempts=[a.model_dump() for a in attempts],
                        tenant_id=tenant_id,
                        customer_reference=customer_reference,
                        mawb_obl_no=mawb_obl_no,
                        hawb_hbl_no=hawb_hbl_no,
                        vessel_name=vessel_name or (successful_result.raw_data.get("vessel_name") if successful_result and successful_result.raw_data else None),
                        flight_no=flight_no,
                        container_number=container_no,
                    )
                else:
                    # Persist provider attempts (cURL commands and responses) even when tracking doesn't yield milestones
                    self.db_tool.record_execution_logs(
                        db=db,
                        tracking_number=route_plan.clean_tracking_number,
                        attempts=[a.model_dump() for a in attempts],
                    )
            except Exception as e:
                logger.error(f"Non-fatal error persisting to database: {e}")

        # Step 5: Formulate final relatable message and status
        if successful_result:
            final_status = successful_result.status
            final_message = f"Shipment tracked successfully via {route_plan.carrier_name}."
        else:
            # --- DB Fallback: return last stored tracking when providers fail ---
            cached = None
            if db:
                try:
                    cached = self.db_tool.get_last_tracking(
                        db=db,
                        tracking_number=route_plan.clean_tracking_number,
                    )
                except Exception as e:
                    logger.error(f"Error fetching cached tracking from DB: {e}")

            if cached and cached.get("events"):
                logger.info(
                    f"Returning cached tracking from DB for '{route_plan.clean_tracking_number}' "
                    f"(last updated: {cached.get('updated_at')})"
                )

                # Rebuild events from cached data
                for ev in cached["events"]:
                    coords = ev.get("coordinates")
                    event_obj = UnifiedTrackingEvent(
                        station=ev.get("station"),
                        status_code=ev.get("status_code"),
                        status_message=ev.get("status_message", "Status update"),
                        event_time=ev.get("event_time"),
                        flight_info=ev.get("flight_info"),
                        pieces=ev.get("pieces"),
                        weight=ev.get("weight"),
                        coordinates=LocationCoordinates(**coords) if coords else None,
                    )
                    events_list.append(event_obj)

                events_list = sort_events_descending(events_list)
                if events_list:
                    latest_event_obj = events_list[0]

                # Build weight dict from cached flat values
                cached_weight = None
                if cached.get("weight") is not None:
                    cached_weight = {
                        "value": cached["weight"],
                        "unit": cached.get("weight_unit", "kg"),
                    }

                cached_orig = cached.get("origin_coordinates")
                cached_dest = cached.get("destination_coordinates")

                return UnifiedTrackingResponse(
                    tracking_number=route_plan.clean_tracking_number,
                    mode=route_plan.mode,
                    carrier=CarrierInfo(
                        code=route_plan.carrier_code,
                        prefix=route_plan.prefix,
                        name=route_plan.carrier_name,
                        mode=route_plan.mode,
                        primary_provider=route_plan.primary_provider,
                        fallback_providers=route_plan.fallback_providers,
                    ),
                    status=cached.get("status", "CACHED"),
                    message=(
                        f"Live tracking from {route_plan.carrier_name} is temporarily unavailable. "
                        f"Showing last known tracking data (updated: {cached.get('updated_at', 'N/A')})."
                    ),
                    origin=cached.get("origin"),
                    destination=cached.get("destination"),
                    origin_coordinates=LocationCoordinates(**cached_orig) if cached_orig else None,
                    destination_coordinates=LocationCoordinates(**cached_dest) if cached_dest else None,
                    pieces=cached.get("pieces"),
                    weight=cached_weight,
                    volume=cached.get("volume"),
                    latest_event=latest_event_obj,
                    events=events_list,
                    agent_trail=AgentDecisionTrail(
                        detected_mode=route_plan.mode,
                        carrier_identified=route_plan.carrier_name,
                        carrier_code=route_plan.carrier_code,
                        provider_plan=providers_to_try,
                        attempts=attempts,
                        final_provider_used=f"db_cache ({cached.get('last_provider_used', 'unknown')})",
                    ),
                    raw_data=None,
                )

            # No cached data either — return the original error response
            # Check if it was a 404 / no records found vs network failure
            is_404 = any(a.http_status == 404 for a in attempts)
            if is_404 or not last_error or "not found" in (last_error or "").lower():
                final_status = "NOT_FOUND"
                final_message = (
                    f"Tracking not found: No shipment records found for {route_plan.clean_tracking_number} on {route_plan.carrier_name}. "
                    "Please verify the tracking number."
                )
            else:
                final_status = "PROVIDER_ERROR"
                final_message = f"Unable to retrieve tracking from {route_plan.carrier_name}: {last_error}"

        orig_match = match_location(successful_result.origin, route_plan.mode) if (successful_result and successful_result.origin) else None
        dest_match = match_location(successful_result.destination, route_plan.mode) if (successful_result and successful_result.destination) else None

        return UnifiedTrackingResponse(
            tracking_number=route_plan.clean_tracking_number,
            mode=route_plan.mode,
            carrier=CarrierInfo(
                code=route_plan.carrier_code,
                prefix=route_plan.prefix,
                name=route_plan.carrier_name,
                mode=route_plan.mode,
                primary_provider=route_plan.primary_provider,
                fallback_providers=route_plan.fallback_providers,
            ),
            status=final_status,
            message=final_message,
            origin=successful_result.origin if successful_result else None,
            destination=successful_result.destination if successful_result else None,
            origin_coordinates=LocationCoordinates(**orig_match) if orig_match else None,
            destination_coordinates=LocationCoordinates(**dest_match) if dest_match else None,
            pieces=successful_result.pieces if successful_result else None,
            weight=successful_result.weight if successful_result else None,
            volume=successful_result.volume if successful_result else None,
            latest_event=latest_event_obj,
            events=events_list,
            agent_trail=AgentDecisionTrail(
                detected_mode=route_plan.mode,
                carrier_identified=route_plan.carrier_name,
                carrier_code=route_plan.carrier_code,
                provider_plan=providers_to_try,
                attempts=attempts,
                final_provider_used=final_provider_used,
            ),
            raw_data=successful_result.raw_data if successful_result else None,
            containers=successful_result.raw_data.get("containers") if (successful_result and successful_result.raw_data) else None,
            mawb_obl_no=mawb_obl_no,
            container_no=container_no,
            hawb_hbl_no=hawb_hbl_no,
            vessel_name=vessel_name or (successful_result.raw_data.get("vessel_name") if successful_result and successful_result.raw_data else None),
            flight_no=flight_no,
        )
