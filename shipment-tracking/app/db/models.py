from datetime import datetime, timezone
from sqlalchemy import (
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


class Carrier(Base):
    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    prefix = Column(String(100), index=True, nullable=True)  # e.g., '160' or 'MSCU,MSMU,MEDU'
    name = Column(String(150), nullable=False)
    mode = Column(String(20), nullable=False)  # 'AIR' or 'SEA'
    primary_provider = Column(String(100), nullable=False)
    fallback_providers = Column(String(255), nullable=True)  # Comma-separated list
    created_at = Column(DateTime, default=utc_now)


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tracking_number = Column(String(100), unique=True, index=True, nullable=False)
    transport_mode = Column(String(20), nullable=False)  # 'AIR' or 'SEA'
    carrier_code = Column(String(50), nullable=True)
    carrier_name = Column(String(150), nullable=True)
    awb_number = Column(String(50), nullable=True)
    container_number = Column(String(50), nullable=True)
    origin = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)
    status = Column(String(100), default="UNKNOWN")
    pieces = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    weight_unit = Column(String(20), default="kg")
    volume = Column(Float, nullable=True)
    latest_event_status = Column(String(255), nullable=True)
    latest_event_time = Column(DateTime, nullable=True)
    last_provider_used = Column(String(100), nullable=True)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    events = relationship("TrackingEvent", back_populates="shipment", cascade="all, delete-orphan")
    execution_logs = relationship("ProviderExecutionLog", back_populates="shipment", cascade="all, delete-orphan")


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
    station = Column(String(255), nullable=True)
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
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    shipment = relationship("Shipment", back_populates="execution_logs")
