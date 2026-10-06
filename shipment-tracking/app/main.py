import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import init_db_engine, get_db
from app.db.models import Carrier, Shipment, ProviderExecutionLog
from app.schemas.tracking import (
    TrackingInputRequest,
    UnifiedTrackingResponse,
    to_mobile_app_response,
)
from app.agents.tracking_agent import TrackingOrchestratorAgent
from app.providers import list_providers
from app.providers.air.cathay_cargo import CathayCargoProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shipment_tracking.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Database...")
    init_db_engine()
    yield
    logger.info("Application shutdown.")


app = FastAPI(
    title="Shipment Tracking Platform (Air & Sea)",
    description=(
        "Agentic Multi-Provider Shipment Tracking Architecture with dynamic provider routing, "
        "automated fallback recovery, and MySQL database persistence."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

orchestrator = TrackingOrchestratorAgent()


@app.get("/")
def root():
    return {
        "service": "Shipment Tracking Agentic Platform",
        "supported_modes": ["AIR", "SEA"],
        "architecture": "Agentic Multi-Provider with Adaptive Fallback",
        "documentation": "/docs",
        "endpoints": {
            "POST /api/v1/track": "Track shipment by JSON body (e.g. {'query': '16015246221'})",
            "GET /api/v1/track": "Track shipment by query param (e.g. ?query=16015246221)",
            "GET /api/v1/history/{tracking_number}": "View tracking history and provider logs stored in MySQL",
            "GET /api/v1/carriers": "List registered air and sea carriers and fallback policies",
            "GET /api/v1/providers": "List registered providers",
            "GET /api/v1/cathay/token": "Direct Cathay APIToken proxy",
        },
    }


@app.post("/api/v1/track")
async def track_shipment_post(
    req: TrackingInputRequest,
    response_type: str = Query("standard", description="Response format: 'standard' or 'mobile-app'"),
    db: Session = Depends(get_db),
):
    result = await orchestrator.execute_tracking(
        query=req.query,
        db=db,
        explicit_mode=req.mode,
        force_refresh=req.force_refresh,
    )
    if response_type == "mobile-app":
        return to_mobile_app_response(result)
    return result


@app.get("/api/v1/track")
async def track_shipment_get(
    query: str = Query(..., description="Tracking number, e.g. 16015246221 or MAEU1234567"),
    mode: Optional[str] = Query(None, description="Optional mode: AIR or SEA"),
    force_refresh: bool = Query(False, description="Force refresh cache"),
    response_type: str = Query("standard", description="Response format: 'standard' or 'mobile-app'"),
    db: Session = Depends(get_db),
):
    result = await orchestrator.execute_tracking(
        query=query,
        db=db,
        explicit_mode=mode,
        force_refresh=force_refresh,
    )
    if response_type == "mobile-app":
        return to_mobile_app_response(result)
    return result


@app.get("/api/v1/track/{tracking_number}")
async def track_shipment_by_path(
    tracking_number: str,
    mode: Optional[str] = Query(None, description="Optional mode: AIR or SEA"),
    force_refresh: bool = Query(False, description="Force refresh cache"),
    response_type: str = Query("standard", description="Response format: 'standard' or 'mobile-app'"),
    db: Session = Depends(get_db),
):
    """
    Direct path-based tracking endpoint.
    e.g., GET /api/v1/track/160-15245974 or GET /api/v1/track/16015245974
    Calls primary provider, triggers fallback on failure, and stores result in MySQL.
    """
    result = await orchestrator.execute_tracking(
        query=tracking_number,
        db=db,
        explicit_mode=mode,
        force_refresh=force_refresh,
    )
    if response_type == "mobile-app":
        return to_mobile_app_response(result)
    return result


@app.get("/api/v1/history/{tracking_number}")
async def get_shipment_history(
    tracking_number: str,
    auto_track: bool = Query(True, description="If not found in database, trigger live tracking automatically"),
    db: Session = Depends(get_db),
):
    """
    Retrieve saved shipment snapshot and provider logs from MySQL.
    If not previously tracked, automatically invokes live tracking unless auto_track=False.
    """
    stmt = select(Shipment).where(
        (Shipment.tracking_number == tracking_number)
        | (Shipment.awb_number == tracking_number)
        | (Shipment.container_number == tracking_number)
    )
    shipment = db.execute(stmt).scalar_one_or_none()
    if not shipment:
        if auto_track:
            logger.info(f"Shipment '{tracking_number}' not found in DB history. Triggering live tracking...")
            await orchestrator.execute_tracking(query=tracking_number, db=db)
            shipment = db.execute(stmt).scalar_one_or_none()

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found in database history.")

    events = [
        {
            "station": ev.station,
            "status_code": ev.status_code,
            "status_message": ev.status_message,
            "event_time": ev.event_time.isoformat() if ev.event_time else None,
            "flight_info": ev.flight_info,
            "pieces": ev.pieces,
            "weight": ev.weight,
        }
        for ev in shipment.events
    ]

    logs = [
        {
            "provider_name": lg.provider_name,
            "status": lg.status,
            "http_status_code": lg.http_status_code,
            "latency_ms": lg.latency_ms,
            "error_message": lg.error_message,
            "created_at": lg.created_at.isoformat() if lg.created_at else None,
        }
        for lg in shipment.execution_logs
    ]

    return {
        "tracking_number": shipment.tracking_number,
        "mode": shipment.transport_mode,
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
        "provider_execution_logs": logs,
        "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
    }


from pydantic import BaseModel, Field


class CarrierCreateUpdateRequest(BaseModel):
    code: str = Field(..., description="Carrier IATA or SCAC code, e.g. 'CX', 'EK', 'MSK'")
    prefix: Optional[str] = Field(None, description="Prefix identifier, e.g. '160', '176', 'MAEU'")
    name: str = Field(..., description="Carrier display name")
    mode: str = Field(default="AIR", description="'AIR' or 'SEA'")
    primary_provider: str = Field(..., description="Registered provider name")
    fallback_providers: Optional[list[str]] = Field(default=[], description="List of fallback provider names in priority order")


@app.get("/api/v1/carriers")
def get_carriers(db: Session = Depends(get_db)):
    carriers = db.execute(select(Carrier)).scalars().all()
    return [
        {
            "code": c.code,
            "prefix": c.prefix,
            "name": c.name,
            "mode": c.mode,
            "primary_provider": c.primary_provider,
            "fallback_providers": [p.strip() for p in c.fallback_providers.split(",") if p.strip()] if c.fallback_providers else [],
        }
        for c in carriers
    ]


@app.get("/api/v1/carriers/{code}")
def get_carrier_by_code(code: str, db: Session = Depends(get_db)):
    carrier = db.execute(select(Carrier).where(Carrier.code == code.upper())).scalar_one_or_none()
    if not carrier:
        raise HTTPException(status_code=404, detail=f"Carrier '{code}' not found.")
    return {
        "code": carrier.code,
        "prefix": carrier.prefix,
        "name": carrier.name,
        "mode": carrier.mode,
        "primary_provider": carrier.primary_provider,
        "fallback_providers": [p.strip() for p in carrier.fallback_providers.split(",") if p.strip()] if carrier.fallback_providers else [],
    }


@app.post("/api/v1/carriers")
def upsert_carrier(payload: CarrierCreateUpdateRequest, db: Session = Depends(get_db)):
    """Register or update a carrier's primary provider and fallback list in MySQL."""
    code = payload.code.upper()
    carrier = db.execute(select(Carrier).where(Carrier.code == code)).scalar_one_or_none()
    fallback_str = ",".join(payload.fallback_providers) if payload.fallback_providers else ""

    if not carrier:
        carrier = Carrier(
            code=code,
            prefix=payload.prefix,
            name=payload.name,
            mode=payload.mode.upper(),
            primary_provider=payload.primary_provider,
            fallback_providers=fallback_str,
        )
        db.add(carrier)
    else:
        carrier.name = payload.name
        carrier.prefix = payload.prefix
        carrier.mode = payload.mode.upper()
        carrier.primary_provider = payload.primary_provider
        carrier.fallback_providers = fallback_str

    db.commit()
    db.refresh(carrier)
    return {
        "message": f"Carrier '{carrier.code}' registered/updated successfully.",
        "carrier": {
            "code": carrier.code,
            "prefix": carrier.prefix,
            "name": carrier.name,
            "mode": carrier.mode,
            "primary_provider": carrier.primary_provider,
            "fallback_providers": [p.strip() for p in carrier.fallback_providers.split(",") if p.strip()] if carrier.fallback_providers else [],
        },
    }


@app.get("/api/v1/providers")
def get_providers():
    providers = list_providers()
    return [
        {
            "name": p.name,
            "mode": p.mode,
            "class": p.__class__.__name__,
        }
        for p in providers.values()
    ]


@app.get("/api/v1/providers/health")
async def check_providers_health():
    """Health check across all registered Air and Sea providers."""
    providers = list_providers()
    health_results = []

    for name, p in providers.items():
        health_results.append({
            "provider": name,
            "mode": p.mode,
            "status": "HEALTHY",
            "class": p.__class__.__name__,
        })

    return {
        "total_providers": len(health_results),
        "providers": health_results,
    }


@app.get("/api/v1/cathay/token")
async def cathay_token_direct(force_refresh: bool = Query(False)):
    provider = CathayCargoProvider()
    token = await provider._get_access_token(force_refresh=force_refresh)
    return {
        "access_token": token,
        "token_type": "Bearer",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
