import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Shipment, TrackingEvent, ProviderExecutionLog

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
    ) -> Shipment:
        try:
            stmt = select(Shipment).where(Shipment.tracking_number == tracking_number)
            shipment = db.execute(stmt).scalar_one_or_none()

            raw_json_str = json.dumps(raw_data, default=str) if raw_data else None

            if not shipment:
                shipment = Shipment(
                    tracking_number=tracking_number,
                    transport_mode=transport_mode,
                    carrier_code=carrier_code,
                    carrier_name=carrier_name,
                    awb_number=tracking_number if transport_mode == "AIR" else None,
                    container_number=tracking_number if transport_mode == "SEA" else None,
                    origin=origin,
                    destination=destination,
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
                shipment.status = status
                shipment.origin = origin or shipment.origin
                shipment.destination = destination or shipment.destination
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

                    t_event = TrackingEvent(
                        shipment_id=shipment.id,
                        station=ev.get("station"),
                        status_code=ev.get("status_code"),
                        status_message=ev.get("status_message"),
                        event_time=event_time,
                        flight_info=ev.get("flight_info"),
                        pieces=ev.get("pieces"),
                        weight=ev.get("weight"),
                    )
                    db.add(t_event)

                latest_ev = events[-1]
                shipment.latest_event_status = latest_ev.get("status_message")

            for att in attempts:
                log_entry = ProviderExecutionLog(
                    shipment_id=shipment.id,
                    tracking_number=tracking_number,
                    provider_name=att.get("provider_name", "unknown"),
                    status=att.get("status", "UNKNOWN"),
                    http_status_code=att.get("http_status"),
                    error_message=att.get("error"),
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
                events.append({
                    "station": ev.station,
                    "status_code": ev.status_code,
                    "status_message": ev.status_message,
                    "event_time": ev.event_time.isoformat() if ev.event_time else None,
                    "flight_info": ev.flight_info,
                    "pieces": ev.pieces,
                    "weight": ev.weight,
                })

            return {
                "tracking_number": shipment.tracking_number,
                "transport_mode": shipment.transport_mode,
                "carrier_code": shipment.carrier_code,
                "carrier_name": shipment.carrier_name,
                "status": shipment.status,
                "origin": shipment.origin,
                "destination": shipment.destination,
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
