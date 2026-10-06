from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TrackingInputRequest(BaseModel):
    query: str = Field(
        ...,
        description="Tracking identifier, e.g. '16015246221', '160-15246221', or 'MSKU1234567'",
        examples=["16015246221", "160-15246221", "MAEU1234567"],
    )
    mode: Optional[str] = Field(
        default=None,
        description="Optional explicit transport mode ('AIR' or 'SEA'). If omitted, agent automatically detects.",
    )
    carrier_code: Optional[str] = Field(
        default=None,
        description="Optional carrier code or airline prefix override (e.g. '160' or 'CX')",
    )
    force_refresh: bool = Field(
        default=False,
        description="Force bypass of cached token or tracking snapshot",
    )


class CarrierInfo(BaseModel):
    code: str
    prefix: Optional[str] = None
    name: str
    mode: str
    primary_provider: str
    fallback_providers: List[str] = []


class UnifiedTrackingEvent(BaseModel):
    station: Optional[str] = None
    status_code: Optional[str] = None
    status_message: str
    event_time: Optional[datetime] = None
    flight_info: Optional[str] = None
    pieces: Optional[int] = None
    weight: Optional[float] = None
    raw_status: Optional[str] = None


class ProviderAttempt(BaseModel):
    provider_name: str
    status: str  # 'SUCCESS', 'FAILED', 'FALLBACK_TRIGGERED'
    http_status: Optional[int] = None
    latency_ms: float
    error: Optional[str] = None


class AgentDecisionTrail(BaseModel):
    detected_mode: str
    carrier_identified: str
    carrier_code: str
    provider_plan: List[str]
    attempts: List[ProviderAttempt] = []
    final_provider_used: Optional[str] = None


class UnifiedTrackingResponse(BaseModel):
    tracking_number: str
    mode: str  # 'AIR' or 'SEA'
    carrier: CarrierInfo
    status: str
    message: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    pieces: Optional[int] = None
    weight: Optional[Dict[str, Any]] = None
    volume: Optional[float] = None
    latest_event: Optional[UnifiedTrackingEvent] = None
    events: List[UnifiedTrackingEvent] = []
    agent_trail: AgentDecisionTrail
    raw_data: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Mobile-App Response Format (flat, lightweight)
# ---------------------------------------------------------------------------

class MobileAppEvent(BaseModel):
    station: Optional[str] = None
    status: str
    statusCode: Optional[str] = None
    time: Optional[str] = None
    flight: Optional[str] = None
    pieces: Optional[str] = None
    weight: Optional[str] = None


class MobileAppResponse(BaseModel):
    awbNumber: str
    mode: str
    carrier: str
    carrierCode: str
    trackingStatus: str
    message: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    pieces: Optional[str] = None
    weight: Optional[str] = None
    weightUnit: Optional[str] = None
    volume: Optional[float] = None
    latestEvent: Optional[str] = None
    latestStation: Optional[str] = None
    latestTime: Optional[str] = None
    events: List[MobileAppEvent] = []


def to_mobile_app_response(resp: UnifiedTrackingResponse) -> dict:
    """Transform a UnifiedTrackingResponse into the flat mobile-app format."""
    # Build flat events list
    mobile_events = []
    for ev in resp.events:
        mobile_events.append(MobileAppEvent(
            station=ev.station,
            status=ev.status_message,
            statusCode=ev.status_code,
            time=ev.event_time.isoformat() if ev.event_time else None,
            flight=ev.flight_info,
            pieces=str(ev.pieces) if ev.pieces is not None else None,
            weight=str(ev.weight) if ev.weight is not None else None,
        ).model_dump())

    # Extract weight value and unit from the nested dict
    weight_value = None
    weight_unit = None
    if resp.weight and isinstance(resp.weight, dict):
        weight_value = resp.weight.get("value")
        weight_unit = resp.weight.get("unit")

    # Remove hyphen from AWB number
    awb_number = resp.tracking_number.replace("-", "")

    mobile = MobileAppResponse(
        awbNumber=awb_number,
        mode=resp.mode,
        carrier=resp.carrier.name,
        carrierCode=resp.carrier.code,
        trackingStatus=resp.status,
        message=resp.message,
        origin=resp.origin,
        destination=resp.destination,
        pieces=str(resp.pieces) if resp.pieces is not None else None,
        weight=str(weight_value) if weight_value is not None else None,
        weightUnit=weight_unit,
        volume=resp.volume,
        latestEvent=resp.latest_event.status_message if resp.latest_event else None,
        latestStation=resp.latest_event.station if resp.latest_event else None,
        latestTime=resp.latest_event.event_time.isoformat() if resp.latest_event and resp.latest_event.event_time else None,
        events=mobile_events,
    )
    return mobile.model_dump()
