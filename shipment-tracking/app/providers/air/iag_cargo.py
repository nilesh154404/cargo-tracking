import time
import httpx
from datetime import datetime
from typing import Dict, Any, List

from app.providers.base import BaseProvider, ProviderResult
import logging

logger = logging.getLogger(__name__)

class IagCargoProvider(BaseProvider):
    name = "iag_cargo"
    mode = "AIR"
    
    async def track(self, tracking_number: str, prefix: str = "", serial: str = "", **kwargs) -> ProviderResult:
        start_time = time.time()
        # Ensure we have the hyphen format if just given 11 digits
        if not tracking_number or len(tracking_number.replace("-", "")) != 11:
            tracking_number = f"{prefix}-{serial}"
            
        url = f"https://api.tracking.iagcargo.com/tracking/{tracking_number}"
        
        headers = {
            "accept": "application/json, text/plain, */*",
            "origin": "https://ui.tracking.iagcargo.com",
            "referer": "https://ui.tracking.iagcargo.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
        }
        
        try:
            logger.info(f"IAG Cargo: Tracking {tracking_number}...")
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                
                awb = data.get("awb", {})
                origin = awb.get("originCode", "")
                dest = awb.get("destinationCode", "")
                pieces = awb.get("totalPackages")
                
                weight_val = awb.get("totalWeight")
                weight_unit = awb.get("unitOfTotalWeight", "K")
                # Normalize weight unit to 'kg' if 'K'
                if weight_unit.upper() in ["K", "KG", "KGS"]:
                    weight_unit = "kg"
                
                weight = None
                if weight_val is not None:
                    weight = {"value": float(weight_val), "unit": weight_unit}
                
                events = []
                # Parse journey stations
                journey_stations = data.get("journeyStations", [])
                for station in journey_stations:
                    for milestone in station.get("milestones", []):
                        code = milestone.get("milestoneCode", "")
                        event_time = milestone.get("eventTime", "")
                        loc_code = milestone.get("location", {}).get("locationCode", "")
                        flight = milestone.get("flightNumber", "")
                        evt_pieces = milestone.get("packages")
                        evt_weight = milestone.get("weight")
                        
                        desc = code
                        if code == "RCS":
                            desc = "Ready for carriage"
                        elif code == "DEP":
                            desc = "Flight departed"
                        elif code == "ARR":
                            desc = "Flight arrived"
                        elif code == "NFD":
                            desc = "Ready for delivery"
                        elif code == "DLV":
                            desc = "Delivered"
                            
                        status_message = desc
                        if flight:
                            status_message += f" (Flight {flight})"
                            
                        # Format the ISO time if needed, though it is usually ISO-ish already (e.g. 2026-08-27T12:21:00.000)
                        if event_time and event_time.endswith("Z"):
                            # some fields use receptionTime with Z, eventTime usually doesn't have Z, just rely on it directly.
                            pass
                        
                        # Fallback to shipment-level pieces/weight if event-level is null
                        final_pieces = evt_pieces if evt_pieces is not None else pieces
                        final_weight = float(evt_weight) if evt_weight is not None else (weight_val if weight_val is not None else None)
                        
                        events.append({
                            "station": loc_code,
                            "status_code": code,
                            "status_message": status_message,
                            "event_time": event_time,
                            "milestone_status": f"{code} - {desc}" if desc != code else code,
                            "raw_status": code,
                            "flight_info": flight,
                            "pieces": final_pieces,
                            "weight": final_weight
                        })
                
                # Sort events chronologically by event_time
                events.sort(key=lambda x: x["event_time"] or "")
                
                status_details = data.get("shipmentStatusDetails", {})
                overall_status = status_details.get("status")
                
                latest_event = events[-1] if events else None
                if not overall_status:
                    overall_status = latest_event.get("status_code", "In Transit") if latest_event else "In Transit"
                
                return ProviderResult(
                    success=True,
                    provider_name=self.name,
                    status_code=200,
                    status=overall_status,
                    origin=origin,
                    destination=dest,
                    pieces=pieces,
                    weight=weight,
                    events=events,
                    latest_event=latest_event,
                    raw_data=data,
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="IAG Cargo tracking request timed out.",
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
        except httpx.HTTPStatusError as exc:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
        except Exception as exc:
            logger.error(f"IAG Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
