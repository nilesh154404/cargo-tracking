from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


class SubscriptionTier(Base):
    __tablename__ = "subscription_tiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, index=True, nullable=False)  # 'developer', 'growth', 'business', 'enterprise'
    name = Column(String(100), nullable=False)
    monthly_credits = Column(Integer, nullable=False, default=100)
    rate_limit_rpm = Column(Integer, nullable=False, default=10)
    max_api_keys = Column(Integer, nullable=False, default=2)
    allow_batch = Column(Boolean, default=False)
    allow_webhooks = Column(Boolean, default=True)
    allow_custom_carriers = Column(Boolean, default=False)
    price_usd_monthly = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utc_now)

    tenants = relationship("Tenant", back_populates="tier")


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    tier_code = Column(String(50), ForeignKey("subscription_tiers.code"), default="developer", nullable=False)
    monthly_quota = Column(Integer, default=100, nullable=False)
    current_usage = Column(Integer, default=0, nullable=False)
    rate_limit_rpm = Column(Integer, default=10, nullable=False)
    allow_overage = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    billing_cycle_start = Column(DateTime, default=utc_now)
    billing_cycle_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    tier = relationship("SubscriptionTier", back_populates="tenants")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="tenant", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="tenant", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="tenant", cascade="all, delete-orphan")
    webhook_endpoints = relationship("WebhookEndpoint", back_populates="tenant", cascade="all, delete-orphan")
    carrier_configs = relationship("TenantCarrierConfig", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String(200), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=True)
    role = Column(String(50), default="ADMIN", nullable=False)  # 'SUPER_ADMIN', 'ADMIN', 'OPERATOR', 'VIEWER'
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    tenant = relationship("Tenant", back_populates="users")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(30), nullable=False, index=True)  # e.g., 'cargotrk_live_9f8a'
    key_hash = Column(String(128), unique=True, index=True, nullable=False)  # SHA-256
    scopes = Column(String(255), default="tracking:live,tracking:read", nullable=False)
    rate_limit_override = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    tenant = relationship("Tenant", back_populates="api_keys")
    usage_records = relationship("UsageRecord", back_populates="api_key")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    tracking_number = Column(String(100), nullable=False)
    transport_mode = Column(String(20), nullable=False)  # 'AIR' or 'SEA'
    carrier_code = Column(String(50), nullable=True)
    credits_consumed = Column(Integer, default=1, nullable=False)
    provider_used = Column(String(100), nullable=True)
    status = Column(String(100), nullable=True)
    request_ip = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    tenant = relationship("Tenant", back_populates="usage_records")
    api_key = relationship("ApiKey", back_populates="usage_records")


class Carrier(Base):
    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    prefix = Column(String(100), index=True, nullable=True)  # e.g., '160' or 'MSCU,MSMU,MEDU,MSDU,MSNU'
    name = Column(String(150), nullable=False)
    mode = Column(String(20), nullable=False)  # 'AIR' or 'SEA'
    primary_provider = Column(String(100), nullable=False)
    fallback_providers = Column(String(255), nullable=True)  # Comma-separated list
    created_at = Column(DateTime, default=utc_now)


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    tracking_number = Column(String(100), unique=True, index=True, nullable=False)
    customer_reference = Column(String(100), nullable=True, index=True)
    transport_mode = Column(String(20), nullable=False)  # 'AIR' or 'SEA'
    carrier_code = Column(String(50), nullable=True)
    carrier_name = Column(String(150), nullable=True)
    awb_number = Column(String(50), nullable=True)
    container_number = Column(String(50), nullable=True)
    mawb_obl_no = Column(String(100), nullable=True)
    hawb_hbl_no = Column(String(100), nullable=True)
    vessel_name = Column(String(150), nullable=True)
    flight_no = Column(String(50), nullable=True)
    origin = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    origin_code = Column(String(50), nullable=True)
    origin_name = Column(String(255), nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    destination_code = Column(String(50), nullable=True)
    destination_name = Column(String(255), nullable=True)
    status = Column(String(100), default="UNKNOWN")
    pieces = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    weight_unit = Column(String(20), default="kg")
    volume = Column(Float, nullable=True)
    latest_event_status = Column(String(255), nullable=True)
    latest_event_time = Column(DateTime, nullable=True)
    last_provider_used = Column(String(100), nullable=True)
    raw_response = Column(Text, nullable=True)
    active_polling_enabled = Column(Boolean, default=False)
    last_polled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    tenant = relationship("Tenant", back_populates="shipments")
    events = relationship("TrackingEvent", back_populates="shipment", cascade="all, delete-orphan")
    execution_logs = relationship("ProviderExecutionLog", back_populates="shipment", cascade="all, delete-orphan")
    webhook_deliveries = relationship("WebhookDelivery", back_populates="shipment", cascade="all, delete-orphan")


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
    station = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_code = Column(String(50), nullable=True)
    location_name = Column(String(255), nullable=True)
    status_code = Column(String(50), nullable=True)  # e.g., RCS, DEP, ARR, DLV
    status_message = Column(String(500), nullable=True)
    event_time = Column(DateTime, nullable=True)
    flight_info = Column(String(100), nullable=True)
    pieces = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    shipment = relationship("Shipment", back_populates="events")


class ProviderExecutionLog(Base):
    __tablename__ = "provider_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True)
    tracking_number = Column(String(100), nullable=False)
    provider_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)  # 'SUCCESS', 'FAILED', 'FALLBACK'
    http_status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    request_curl = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    shipment = relationship("Shipment", back_populates="execution_logs")


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    secret_token = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    subscribed_events = Column(String(255), default="shipment.status_updated,shipment.delivered", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    tenant = relationship("Tenant", back_populates="webhook_endpoints")
    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_id = Column(Integer, ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False)
    http_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")
    shipment = relationship("Shipment", back_populates="webhook_deliveries")


class TenantCarrierConfig(Base):
    __tablename__ = "tenant_carrier_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    carrier_code = Column(String(50), nullable=False)
    custom_primary_provider = Column(String(100), nullable=True)
    custom_fallback_providers = Column(String(255), nullable=True)
    custom_credentials = Column(Text, nullable=True)  # Stored encrypted or JSON string
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    tenant = relationship("Tenant", back_populates="carrier_configs")


class LocationCoordinate(Base):
    __tablename__ = "location_coordinates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_type = Column(String(20), index=True, nullable=False)  # 'AIRPORT' or 'SEAPORT'
    code = Column(String(50), index=True, nullable=False)           # Normalized uppercase: 'HKG', 'INVTZ', 'BEANR'
    display_code = Column(String(50), nullable=True)                # Original: 'BE ANR' or 'HKG'
    icao_code = Column(String(20), index=True, nullable=True)       # For airports: 'VHHH', 'OAKN'
    name = Column(String(255), index=True, nullable=False)          # Full airport / port name
    city = Column(String(150), index=True, nullable=True)           # City / municipality / metro
    country = Column(String(150), index=True, nullable=True)        # Country name
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    source = Column(String(100), nullable=False)                    # 'global_cargo_airports.xlsx' or 'world_seaports.xlsx'
    metadata_json = Column(Text, nullable=True)                     # Extra details (category, status, continent)
    created_at = Column(DateTime, default=utc_now)
