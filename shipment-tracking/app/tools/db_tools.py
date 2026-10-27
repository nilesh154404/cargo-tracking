import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Shipment, TrackingEvent, ProviderExecutionLog
from app.schemas.tracking import sort_events_descending
from app.services.location_matcher import match_location

logger = logging.getLogger("shipment_tracking.tools.db")


class DatabasePersistenceTool:
    """Tool used by agents to record shipment status, events, and provider execution logs in MySQL."""

    name = "persist_tracking_snapshot"
    description = "Persists unified tracking data and provider fallback logs to the MySQL database."

    @classmethod
    def save_snapshot(
        cls,
        db: Session,
        tracking_number: str,
        transport_mode: str,
        carrier_code: str,
        carrier_name: str,
        status: str,
        origin: Optional[str],
        destination: Optional[str],
        pieces: Optional[int],
        weight_val: Optional[float],
        weight_unit: Optional[str],
        volume: Optional[float],
        provider_used: str,
        events: List[Dict[str, Any]],
        raw_data: Optional[Dict[str, Any]],
        attempts: List[Dict[str, Any]],
        tenant_id: Optional[int] = None,
        customer_reference: Optional[str] = None,
        mawb_obl_no: Optional[str] = None,
        hawb_hbl_no: Optional[str] = None,
        vessel_name: Optional[str] = None,
        flight_no: Optional[str] = None,
        container_number: Optional[str] = None,
    ) -> Shipment:
        try:
            stmt = select(Shipment).where(Shipment.tracking_number == tracking_number)
            shipment = db.execute(stmt).scalar_one_or_none()

            raw_json_str = json.dumps(raw_data, default=str) if raw_data else None

            # Resolve coordinates for origin and destination
            orig_match = match_location(origin, transport_mode) if origin else None
            dest_match = match_location(destination, transport_mode) if destination else None

            if not shipment:
                shipment = Shipment(
                    tenant_id=tenant_id,
                    customer_reference=customer_reference,
                    tracking_number=tracking_number,
                    transport_mode=transport_mode,
                    carrier_code=carrier_code,
                    carrier_name=carrier_name,
                    awb_number=tracking_number if transport_mode == "AIR" else None,
                    container_number=container_number or (tracking_number if transport_mode == "SEA" else None),
                    mawb_obl_no=mawb_obl_no or (tracking_number if transport_mode == "AIR" else None),
                    hawb_hbl_no=hawb_hbl_no,
                    vessel_name=vessel_name,
                    flight_no=flight_no,
                    origin=origin,
                    destination=destination,
                    origin_lat=orig_match["lat"] if orig_match else None,
                    origin_lng=orig_match["lng"] if orig_match else None,
                    origin_code=orig_match["matched_code"] if orig_match else None,
                    origin_name=orig_match["matched_name"] if orig_match else None,
                    destination_lat=dest_match["lat"] if dest_match else None,
                    destination_lng=dest_match["lng"] if dest_match else None,
                    destination_code=dest_match["matched_code"] if dest_match else None,
                    destination_name=dest_match["matched_name"] if dest_match else None,
                    status=status,
                    pieces=pieces,
                    weight=weight_val,
                    weight_unit=weight_unit or "kg",
                    volume=volume,
                    last_provider_used=provider_used,
                    raw_response=raw_json_str,
                )
                db.add(shipment)
                db.flush()
            else:
                if tenant_id:
                    shipment.tenant_id = tenant_id
                if customer_reference:
                    shipment.customer_reference = customer_reference
                if mawb_obl_no:
                    shipment.mawb_obl_no = mawb_obl_no
                if hawb_hbl_no:
                    shipment.hawb_hbl_no = hawb_hbl_no
                if vessel_name:
                    shipment.vessel_name = vessel_name
                if flight_no:
                    shipment.flight_no = flight_no
                if container_number:
                    shipment.container_number = container_number
                shipment.status = status
                shipment.origin = origin or shipment.origin
                shipment.destination = destination or shipment.destination
                if orig_match:
                    shipment.origin_lat = orig_match["lat"]
                    shipment.origin_lng = orig_match["lng"]
                    shipment.origin_code = orig_match["matched_code"]
                    shipment.origin_name = orig_match["matched_name"]
                if dest_match:
                    shipment.destination_lat = dest_match["lat"]
                    shipment.destination_lng = dest_match["lng"]
                    shipment.destination_code = dest_match["matched_code"]
                    shipment.destination_name = dest_match["matched_name"]
                shipment.pieces = pieces or shipment.pieces
                shipment.weight = weight_val or shipment.weight
                shipment.volume = volume or shipment.volume
                shipment.last_provider_used = provider_used
                shipment.raw_response = raw_json_str
                shipment.updated_at = datetime.now(timezone.utc)

            if events:
                shipment.events.clear()
                for ev in events:
                    event_time = None
                    raw_time = ev.get("event_time")
                    if raw_time:
                        try:
                            event_time = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                        except Exception:
                            event_time = None

                    st = ev.get("station")
                    ev_match = match_location(st, transport_mode) if st else None
                    if ev_match and "coordinates" not in ev:
                        ev["coordinates"] = ev_match

                    t_event = TrackingEvent(
                        shipment_id=shipment.id,
                        station=st,
                        latitude=ev_match["lat"] if ev_match else None,
                        longitude=ev_match["lng"] if ev_match else None,
                        location_code=ev_match["matched_code"] if ev_match else None,
                        location_name=ev_match["matched_name"] if ev_match else None,
                        status_code=ev.get("status_code"),
                        status_message=ev.get("status_message"),
                        event_time=event_time,
                        flight_info=ev.get("flight_info"),
                        pieces=ev.get("pieces"),
                        weight=ev.get("weight"),
                    )
                    db.add(t_event)

                sorted_desc = sort_events_descending(events)
                latest_ev = sorted_desc[0] if sorted_desc else {}
                shipment.latest_event_status = latest_ev.get("status_message")

            for att in attempts:
                # Truncate response_body to avoid exceeding TEXT column limits
                resp_body = att.get("response_body")
                if resp_body and len(resp_body) > 65000:
                    resp_body = resp_body[:65000] + "\n... [TRUNCATED]"

                log_entry = ProviderExecutionLog(
                    shipment_id=shipment.id,
                    tracking_number=tracking_number,
                    provider_name=att.get("provider_name", "unknown"),
                    status=att.get("status", "UNKNOWN"),
                    http_status_code=att.get("http_status"),
                    error_message=att.get("error"),
                    request_curl=att.get("request_curl"),
                    response=resp_body,
                    latency_ms=att.get("latency_ms", 0.0),
                )
                db.add(log_entry)

            db.commit()
            db.refresh(shipment)
            return shipment

        except Exception as exc:
            db.rollback()
            logger.error(f"Error persisting tracking snapshot to DB: {exc}")
            raise exc

    @classmethod
    def record_execution_logs(
        cls,
        db: Session,
        tracking_number: str,
        attempts: List[Dict[str, Any]],
        shipment_id: Optional[int] = None,
    ):
        """Persists provider execution attempts (cURL and responses) to MySQL even when tracking does not yield milestones."""
        try:
            if shipment_id is None:
                stmt = select(Shipment.id).where(Shipment.tracking_number == tracking_number)
                shipment_id = db.execute(stmt).scalar_one_or_none()

            for att in attempts:
                resp_body = att.get("response_body")
                if resp_body and len(resp_body) > 65000:
                    resp_body = resp_body[:65000] + "\n... [TRUNCATED]"

                log_entry = ProviderExecutionLog(
                    shipment_id=shipment_id,
                    tracking_number=tracking_number,
                    provider_name=att.get("provider_name", "unknown"),
                    status=att.get("status", "UNKNOWN"),
                    http_status_code=att.get("http_status"),
                    error_message=att.get("error"),
                    request_curl=att.get("request_curl"),
                    response=resp_body,
                    latency_ms=att.get("latency_ms", 0.0),
                )
                db.add(log_entry)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(f"Error recording execution logs to DB: {exc}")

    @classmethod
    def get_last_tracking(
        cls,
        db: Session,
        tracking_number: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the last stored tracking snapshot from the database.

        Returns a dict with shipment data and events, or None if not found.
        Used as a fallback when all live providers fail.
        """
        try:
            stmt = select(Shipment).where(
                (Shipment.tracking_number == tracking_number)
                | (Shipment.awb_number == tracking_number)
                | (Shipment.container_number == tracking_number)
            )
            shipment = db.execute(stmt).scalar_one_or_none()

            if not shipment:
                return None

            events = []
            for ev in shipment.events:
                coords = None
                if ev.latitude is not None and ev.longitude is not None:
                    coords = {
                        "lat": ev.latitude,
                        "lng": ev.longitude,
                        "matched_code": ev.location_code,
                        "matched_name": ev.location_name,
                        "location_type": shipment.transport_mode,
                    }
                elif ev.station:
                    coords = match_location(ev.station, shipment.transport_mode)

                events.append({
                    "station": ev.station,
                    "status_code": ev.status_code,
                    "status_message": ev.status_message,
                    "event_time": ev.event_time.isoformat() if ev.event_time else None,
                    "flight_info": ev.flight_info,
                    "pieces": ev.pieces,
                    "weight": ev.weight,
                    "coordinates": coords,
                })

            events = sort_events_descending(events)

            orig_coords = None
            if shipment.origin_lat is not None and shipment.origin_lng is not None:
                orig_coords = {
                    "lat": shipment.origin_lat,
                    "lng": shipment.origin_lng,
                    "matched_code": shipment.origin_code,
                    "matched_name": shipment.origin_name,
                    "location_type": shipment.transport_mode,
                }
            elif shipment.origin:
                orig_coords = match_location(shipment.origin, shipment.transport_mode)

            dest_coords = None
            if shipment.destination_lat is not None and shipment.destination_lng is not None:
                dest_coords = {
                    "lat": shipment.destination_lat,
                    "lng": shipment.destination_lng,
                    "matched_code": shipment.destination_code,
                    "matched_name": shipment.destination_name,
                    "location_type": shipment.transport_mode,
                }
            elif shipment.destination:
                dest_coords = match_location(shipment.destination, shipment.transport_mode)

            return {
                "tracking_number": shipment.tracking_number,
                "transport_mode": shipment.transport_mode,
                "carrier_code": shipment.carrier_code,
                "carrier_name": shipment.carrier_name,
                "status": shipment.status,
                "origin": shipment.origin,
                "destination": shipment.destination,
                "origin_coordinates": orig_coords,
                "destination_coordinates": dest_coords,
                "pieces": shipment.pieces,
                "weight": shipment.weight,
                "weight_unit": shipment.weight_unit,
                "volume": shipment.volume,
                "last_provider_used": shipment.last_provider_used,
                "events": events,
                "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
            }

        except Exception as exc:
            logger.error(f"Error retrieving last tracking from DB: {exc}")
            return None
