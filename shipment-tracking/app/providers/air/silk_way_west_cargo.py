import time
import httpx
from datetime import datetime
from typing import Dict, Any, List

from app.providers.base import BaseProvider, ProviderResult
import logging

logger = logging.getLogger(__name__)

class SilkWayWestCargoProvider(BaseProvider):
    name = "silk_way_west_cargo"
    mode = "AIR"
    
    async def track(self, tracking_number: str, prefix: str = "", serial: str = "", **kwargs) -> ProviderResult:
        start_time = time.time()
        
        info_url = f"https://sww.enxt.solutions/api/TrackAndTrace/{prefix}-{serial}"
        events_url = f"https://sww.enxt.solutions/api/Messages/GetFSUData?prefix={prefix}&serial={serial}"
        
        try:
            logger.info(f"Silk Way West Cargo: Tracking {prefix}-{serial}...")
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                info_resp = await client.get(info_url)
                info_resp.raise_for_status()
                info_data = info_resp.json()
                
                events_resp = await client.get(events_url)
                events_resp.raise_for_status()
                events_data = events_resp.json()
                
                origin = ""
                dest = ""
                pieces = info_data.get("pieces")
                
                # Fetch weight
                weight = None
                if info_data.get("actualWeight"):
                    weight = {"value": float(info_data.get("actualWeight")), "unit": "kg"}
                
                # Identify origin/destination from routes if available
                routes = info_data.get("routes", [])
                airports = {a["id"]: a["iataCode"] for a in info_data.get("airports", []) if "id" in a and "iataCode" in a}
                if routes:
                    first_route_origin_id = routes[0].get("origin")
                    last_route_dest_id = routes[-1].get("destination")
                    origin = airports.get(first_route_origin_id, "")
                    dest = airports.get(last_route_dest_id, "")

                events = []
                # Sort events by timestamp or sequence if needed, but the list usually comes in reverse or chronological.
                # The data shows latest events first maybe, or we should sort by Time_Stamp
                # Actually, in the user's snippet, DEP is at the top (Sep 24) and earlier ones are below.
                # Let's sort them ascending by date.
                for ev in events_data:
                    ts = ev.get("Time_Stamp")
                    station = ev.get("Origin_IATA", "")
                    milestone = ev.get("FSU_Code", "")
                    desc = ev.get("FSU_Description", "")
                    flight = ev.get("Flight_Number", "")
                    carrier = ev.get("Carrier_Code", "")
                    
                    flight_info = f"{carrier}{flight}" if carrier and flight else ""
                    
                    status_message = desc or milestone
                    if flight_info:
                        status_message += f" (Flight {flight_info})"
                        
                    events.append({
                        "station": station,
                        "status_code": milestone,
                        "status_message": status_message,
                        "event_time": ts,
                        "milestone_status": f"{milestone} - {desc}" if desc else milestone,
                        "raw_status": milestone,
                        "flight_info": flight_info,
                        "pieces": pieces,
                        "weight": weight["value"] if weight else None
                    })
                
                # Sort events chronologically (oldest to newest)
                events.sort(key=lambda x: x["event_time"] or "")
                
                latest_event = events[-1] if events else None
                overall_status = "In Transit"
                if latest_event:
                    overall_status = latest_event.get("status_code", "In Transit")
                    # If origin/dest are empty, fallback to events
                    if not origin and events:
                        origin = events[0].get("station", "")
                    if not dest and events:
                        dest = events[-1].get("station", "")
                    
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
                    raw_data={"info": info_data, "events": events_data},
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Silk Way West Cargo tracking request timed out.",
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
            logger.error(f"Silk Way West Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
