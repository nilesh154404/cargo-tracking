import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


def sort_events_descending(events: list) -> list:
    """Sort a list of events (UnifiedTrackingEvent, MobileAppEvent, or dicts)
    in descending order (newest/most recent milestone first).
    If events lack timestamps or have identical timestamps, later chronological milestones come first.
    """
    if not events or len(events) <= 1:
        return list(events) if events else []

    def _extract_datetime(ev) -> Optional[datetime]:
        if isinstance(ev, dict):
            raw = ev.get("event_time") or ev.get("time") or ev.get("dateTime")
        else:
            raw = getattr(ev, "event_time", None) or getattr(ev, "time", None)

        if not raw:
            return None
        if isinstance(raw, datetime):
            return raw
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None

    def _to_utc_timestamp(dt: Optional[datetime]) -> float:
        if dt is None:
            return float("-inf")
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            return dt.replace(tzinfo=timezone.utc).timestamp()
        return dt.astimezone(timezone.utc).timestamp()

    first_ts = None
    last_ts = None
    for ev in events:
        ts = _to_utc_timestamp(_extract_datetime(ev))
        if ts != float("-inf"):
            if first_ts is None:
                first_ts = ts
            last_ts = ts

    is_already_descending = False
    if first_ts is not None and last_ts is not None and first_ts > last_ts:
        is_already_descending = True

    result = list(events)
    if not is_already_descending:
        result.reverse()

    result.sort(key=lambda x: _to_utc_timestamp(_extract_datetime(x)), reverse=True)
    return result


class TrackingInputRequest(BaseModel):
    MAWB_OBL_NO: Optional[str] = Field(
        default=None,
        description="Master Air Waybill (e.g. 160-15246221) or Ocean Bill of Lading / Booking Number (e.g. ONEYBLRG06172700)",
    )
    CONTAINER_NO: Optional[str] = Field(
        default=None,
        description="Ocean shipping container number (e.g. ONEU2157736, MSMU6484830)",
    )
    CARRIER_CODE: Optional[str] = Field(
        default=None,
        description="Optional carrier code (e.g. ONE, MSK, CX, EK)",
    )
    CARRIER_NAME: Optional[str] = Field(
        default=None,
        description="Optional carrier name (e.g. Ocean Network Express, Cathay Pacific)",
    )
    VESSEL_NAME: Optional[str] = Field(
        default=None,
        description="Optional vessel name for ocean shipments (e.g. X-PRESS KARAKORAM)",
    )
    HAWB_HBL_NO: Optional[str] = Field(
        default=None,
        description="Optional House Air Waybill or House Bill of Lading Number",
    )
    FLIGHT_NO: Optional[str] = Field(
        default=None,
        description="Optional flight number for air cargo (e.g. CX0802)",
    )
    mode: Optional[str] = Field(
        default=None,
        description="Optional explicit transport mode ('AIR' or 'SEA'). If omitted, agent automatically detects.",
    )
    force_refresh: bool = Field(
        default=False,
        description="Force bypass of cached token or tracking snapshot",
    )
    customer_reference: Optional[str] = Field(
        default=None,
        description="Optional customer PO, invoice, or booking reference",
    )
    search_type: Optional[str] = Field(
        default=None,
        description="Optional carrier search type override (e.g. CNTR_NO, BKG_NO, PO_NO)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "MAWB_OBL_NO": "ONEYBLRG06172700",
                "CONTAINER_NO": "ONEU2157736",
                "CARRIER_CODE": "ONE",
                "CARRIER_NAME": "Ocean Network Express",
                "VESSEL_NAME": "X-PRESS KARAKORAM",
                "HAWB_HBL_NO": "HBL100293",
                "FLIGHT_NO": "CX0802",
                "mode": "SEA",
                "force_refresh": False,
                "customer_reference": "PO-99201",
                "search_type": "CNTR_NO",
            }
        }
    }

    # Programmatic backward-compatible properties (not exposed as separate duplicate fields in OpenAPI schema)
    @property
    def mawb_obl_no(self) -> Optional[str]:
        return self.MAWB_OBL_NO

    @property
    def container_no(self) -> Optional[str]:
        return self.CONTAINER_NO

    @property
    def carrier_code(self) -> Optional[str]:
        return self.CARRIER_CODE

    @property
    def carrier_name(self) -> Optional[str]:
        return self.CARRIER_NAME

    @property
    def vessel_name(self) -> Optional[str]:
        return self.VESSEL_NAME

    @property
    def hawb_hbl_no(self) -> Optional[str]:
        return self.HAWB_HBL_NO

    @property
    def flight_no(self) -> Optional[str]:
        return self.FLIGHT_NO

    @property
    def query(self) -> str:
        return self.CONTAINER_NO or self.MAWB_OBL_NO or ""

    @property
    def tracking_number(self) -> str:
        return self.query

    @model_validator(mode="before")
    @classmethod
    def validate_tracking_input(cls, data: Any):
        if isinstance(data, dict):
            # Check for uppercase or lowercase or legacy keys
            mawb = data.get("MAWB_OBL_NO") or data.get("mawb_obl_no")
            cntr = data.get("CONTAINER_NO") or data.get("container_no")
            c_code = data.get("CARRIER_CODE") or data.get("carrier_code")
            c_name = data.get("CARRIER_NAME") or data.get("carrier_name")
            v_name = data.get("VESSEL_NAME") or data.get("vessel_name")
            h_no = data.get("HAWB_HBL_NO") or data.get("hawb_hbl_no")
            f_no = data.get("FLIGHT_NO") or data.get("flight_no")
            legacy_q = data.get("query") or data.get("tracking_number")

            if legacy_q and not mawb and not cntr:
                cleaned_q = str(legacy_q).strip().upper()
                if bool(re.match(r"^[A-Z]{4}\d{7}$", cleaned_q)) or cleaned_q.startswith("ONEU"):
                    cntr = legacy_q
                else:
                    mawb = legacy_q

            if not mawb and not cntr:
                raise ValueError("Either MAWB_OBL_NO or CONTAINER_NO is required to track a shipment.")

            cleaned = {}
            if mawb:
                cleaned["MAWB_OBL_NO"] = mawb
            if cntr:
                cleaned["CONTAINER_NO"] = cntr
            if c_code:
                cleaned["CARRIER_CODE"] = c_code
            if c_name:
                cleaned["CARRIER_NAME"] = c_name
            if v_name:
                cleaned["VESSEL_NAME"] = v_name
            if h_no:
                cleaned["HAWB_HBL_NO"] = h_no
            if f_no:
                cleaned["FLIGHT_NO"] = f_no
            if "mode" in data and data["mode"] is not None:
                cleaned["mode"] = data["mode"]
            if "force_refresh" in data and data["force_refresh"] is not None:
                cleaned["force_refresh"] = data["force_refresh"]
            if "customer_reference" in data and data["customer_reference"] is not None:
                cleaned["customer_reference"] = data["customer_reference"]
            if "search_type" in data and data["search_type"] is not None:
                cleaned["search_type"] = data["search_type"]
            return cleaned
        return data


class CarrierInfo(BaseModel):
    code: str
    prefix: Optional[str] = None
    name: str
    mode: str
    primary_provider: str
    fallback_providers: List[str] = []


class LocationCoordinates(BaseModel):
    lat: float
    lng: float
    matched_code: Optional[str] = None
    matched_name: Optional[str] = None
    location_type: Optional[str] = None  # "AIRPORT" or "SEAPORT"
    city: Optional[str] = None
    country: Optional[str] = None


class UnifiedTrackingEvent(BaseModel):
    station: Optional[str] = None
    status_code: Optional[str] = None
    status_message: str
    event_time: Optional[datetime] = None
    flight_info: Optional[str] = None
    pieces: Optional[int] = None
    weight: Optional[float] = None
    raw_status: Optional[str] = None
    coordinates: Optional[LocationCoordinates] = None
    active: bool = False
    is_active: bool = False


class ProviderAttempt(BaseModel):
    provider_name: str
    status: str  # 'SUCCESS', 'FAILED', 'FALLBACK_TRIGGERED'
    http_status: Optional[int] = None
    latency_ms: float
    error: Optional[str] = None
    request_curl: Optional[str] = None
    response_body: Optional[str] = None


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
    origin_coordinates: Optional[LocationCoordinates] = None
    destination_coordinates: Optional[LocationCoordinates] = None
    pieces: Optional[int] = None
    weight: Optional[Dict[str, Any]] = None
    volume: Optional[float] = None
    latest_event: Optional[UnifiedTrackingEvent] = None
    events: List[UnifiedTrackingEvent] = []
    agent_trail: AgentDecisionTrail
    raw_data: Optional[Dict[str, Any]] = None
    containers: Optional[List[Dict[str, Any]]] = None
    mawb_obl_no: Optional[str] = None
    container_no: Optional[str] = None
    hawb_hbl_no: Optional[str] = None
    vessel_name: Optional[str] = None
    flight_no: Optional[str] = None

    @model_validator(mode="after")
    def ensure_events_descending(self) -> "UnifiedTrackingResponse":
        if self.events:
            self.events = sort_events_descending(self.events)
            if self.latest_event is None and self.events:
                self.latest_event = self.events[0]
        return self


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
    lat: Optional[float] = None
    lng: Optional[float] = None
    locationName: Optional[str] = None
    is_active: bool = False
    raw_status: Optional[str] = None


class MobileAppResponse(BaseModel):
    awbNumber: str
    mode: str
    carrier: str
    carrierCode: str
    trackingStatus: str
    message: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    originCoordinates: Optional[Dict[str, Any]] = None
    destinationCoordinates: Optional[Dict[str, Any]] = None
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
    # Build flat events list in descending order
    sorted_events = sort_events_descending(resp.events)
    mobile_events = []
    for ev in sorted_events:
        coords = ev.coordinates.model_dump() if ev.coordinates else None
        is_act = bool(getattr(ev, "is_active", False) or getattr(ev, "active", False))
        r_status = getattr(ev, "raw_status", None)
        mobile_events.append(MobileAppEvent(
            station=ev.station,
            status=ev.status_message,
            statusCode=ev.status_code,
            time=ev.event_time.isoformat() if ev.event_time else None,
            flight=ev.flight_info,
            pieces=str(ev.pieces) if ev.pieces is not None else None,
            weight=str(ev.weight) if ev.weight is not None else None,
            lat=coords.get("lat") if coords else None,
            lng=coords.get("lng") if coords else None,
            locationName=coords.get("matched_name") if coords else None,
            is_active=is_act,
            raw_status=r_status,
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
        originCoordinates=resp.origin_coordinates.model_dump() if resp.origin_coordinates else None,
        destinationCoordinates=resp.destination_coordinates.model_dump() if resp.destination_coordinates else None,
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


# ---------------------------------------------------------------------------
# Enterprise & Subscription Management Schemas
# ---------------------------------------------------------------------------

class RegisterOrganizationRequest(BaseModel):
    name: str = Field(..., description="Organization name, e.g. 'Apex Global Freight'")
    slug: str = Field(..., description="Unique organization slug identifier, e.g. 'apex-freight'")
    email: str = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Admin password")
    full_name: Optional[str] = Field(None, description="Admin full name")
    tier_code: str = Field(default="developer", description="Initial plan tier: developer, growth, business, enterprise")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    tenant_id: Optional[int] = None
    tenant_slug: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: Optional[UserResponse] = None
    tenant: Optional[Dict[str, Any]] = None


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., description="Descriptive name for the API key, e.g. 'TMS Production Integration'")
    scopes: Optional[List[str]] = Field(
        default=["tracking:live", "tracking:read"],
        description="Allowed scopes: tracking:live, tracking:read, shipments:batch, webhooks:write, admin:manage",
    )
    rate_limit_override: Optional[int] = Field(None, description="Optional custom RPM limit")
    expires_in_days: Optional[int] = Field(None, description="Optional expiration in days")


class ApiKeyCreatedResponse(BaseModel):
    id: int
    name: str
    key: str = Field(..., description="Full secret API key. Store this securely; it will not be displayed again.")
    secret_key: Optional[str] = None
    prefix: str
    key_prefix: Optional[str] = None
    scopes: List[str]
    created_at: str


class ApiKeyInfoResponse(BaseModel):
    id: int
    name: str
    prefix: str
    key_prefix: Optional[str] = None
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[str]
    created_at: str
    created_at: str


class SubscriptionPlanResponse(BaseModel):
    code: str
    name: str
    monthly_credits: int
    rate_limit_rpm: int
    max_api_keys: int
    allow_batch: bool
    allow_webhooks: bool
    allow_custom_carriers: bool
    price_usd_monthly: float


class TenantUsageResponse(BaseModel):
    tenant_slug: str
    tenant_name: str
    tier_code: str
    monthly_quota: int
    current_usage: int
    remaining_credits: int
    usage_percentage: float
    rate_limit_rpm: int
    allow_overage: bool


class UpgradePlanRequest(BaseModel):
    tier_code: str = Field(..., description="New plan tier: developer, growth, business, enterprise")


class BatchTrackingRequest(BaseModel):
    items: List[TrackingInputRequest] = Field(..., min_length=1, max_length=100)


class BatchTrackingResponse(BaseModel):
    total_requested: int
    total_processed: int
    credits_consumed: int
    results: List[UnifiedTrackingResponse]


class AdminCreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Organization name")
    slug: str = Field(..., min_length=2, max_length=60, description="Unique organization slug identifier")
    tier_code: str = Field(default="growth", description="Plan tier: developer, growth, business, enterprise")
    admin_email: str = Field(..., description="Root admin email for the tenant")
    admin_password: str = Field(..., min_length=8, description="Initial root admin password")
    admin_name: Optional[str] = Field(None, description="Admin full name")
    monthly_quota: Optional[int] = Field(None, description="Custom monthly quota override")
    rate_limit_rpm: Optional[int] = Field(None, description="Custom rate limit RPM override")
    allow_overage: bool = Field(default=False, description="Allow overage usage beyond quota")


class AdminTenantCreatedResponse(BaseModel):
    message: str
    tenant: dict
    admin_user: dict
    api_key: dict


class AdminResetTenantPasswordRequest(BaseModel):
    user_id: Optional[int] = Field(None, description="Optional specific user ID under this tenant to reset. Defaults to primary admin.")
    new_password: Optional[str] = Field(None, min_length=6, max_length=128, description="Optional new password. If omitted, a secure random password is generated.")


class AdminResetPasswordResponse(BaseModel):
    status: str = "success"
    message: str
    tenant_id: int
    tenant_name: str
    user_id: int
    user_email: str
    new_password: str



