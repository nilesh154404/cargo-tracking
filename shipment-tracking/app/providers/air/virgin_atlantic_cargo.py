import time
import httpx
from datetime import datetime
from typing import Dict, Any, List

from app.providers.base import BaseProvider, ProviderResult
import logging

logger = logging.getLogger(__name__)

class VirginAtlanticCargoProvider(BaseProvider):
    name = "virgin_atlantic_cargo"
    mode = "AIR"
    
    async def track(self, tracking_number: str, prefix: str = "", serial: str = "", **kwargs) -> ProviderResult:
        start_time = time.time()
        
        # Format the AWB (removing hyphens)
        clean_awb = tracking_number.replace("-", "")
        if not clean_awb and prefix and serial:
            clean_awb = f"{prefix}{serial}"
            
        try:
            logger.info(f"Virgin Atlantic Cargo: Tracking {tracking_number}...")
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                # 1. Fetch token
                token_url = f"https://myvs.virginatlanticcargo.com/api/uaa/guest/oauth/token?productName=offerandorder&_time={int(time.time() * 1000)}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
                    "Authorization": "Basic bWVyY2F0b3I6",
                    "app-id": "OO002",
                    "x-tenant": "VS",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://myvs.virginatlanticcargo.com",
                    "Referer": "https://myvs.virginatlanticcargo.com/app/offerandorder/"
                }
                
                data = "tenant=VS&client_id=mercator&client_secret="
                
                resp = await client.post(token_url, headers=headers, content=data)
                resp.raise_for_status()
                
                token = resp.json().get("access_token")
                if not token:
                    raise Exception("Failed to retrieve access token")
                
                # 2. Search AWB to get Order Reference
                search_url = "https://myvs.virginatlanticcargo.com/api/order/services/cargo/v1/orders/actions/search?view=summary"
                search_headers = headers.copy()
                search_headers["Authorization"] = f"Bearer {token}"
                search_headers["Content-Type"] = "application/json"
                
                search_payload = {
                    "orderFilter": {
                        "airCapacity": {
                            "documentNumbers": [clean_awb],
                            "includeItinerary": False
                        }
                    },
                    "pageRequest": {
                        "page": 1,
                        "pageSize": 10
                    }
                }
                
                search_resp = await client.post(search_url, headers=search_headers, json=search_payload)
                search_resp.raise_for_status()
                search_data = search_resp.json()
                
                orders = search_data.get("data", {}).get("order", [])
                if not orders:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        error=f"No shipment found for AWB {tracking_number}",
                        latency_ms=round((time.time() - start_time) * 1000, 2)
                    )
                    
                order_items = orders[0].get("orderItems", {}).get("orderItem", [])
                if not order_items:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        error=f"No order items found for AWB {tracking_number}",
                        latency_ms=round((time.time() - start_time) * 1000, 2)
                    )
                    
                order_ref = order_items[0].get("reference", {}).get("bookingReferenceNumber")
                if not order_ref:
                    raise Exception("Could not find booking reference number")
                
                # 3. Get Details
                details_url = f"https://myvs.virginatlanticcargo.com/api/order/services/cargo/v1/orders/b{order_ref}"
                details_resp = await client.get(details_url, headers=search_headers)
                details_resp.raise_for_status()
                details_data = details_resp.json()
                
                items = details_data.get("data", {}).get("orderItems", {}).get("orderItem", [])
                if not items:
                    raise Exception("Details data missing orderItem")
                    
                item = items[0]
                
                # Extract Origin / Destination / Weight / Pieces
                air_cap = item.get("productInfo", {}).get("airCapacity", {})
                origin = air_cap.get("origin", {}).get("code")
                dest = air_cap.get("destination", {}).get("code")
                
                cargo_info = air_cap.get("cargoInfo", {})
                qty_info = cargo_info.get("quantityInfo", [{}])
                total_pieces = qty_info[0].get("piece")
                
                weight_val = qty_info[0].get("weight", {}).get("value")
                weight_unit = qty_info[0].get("weight", {}).get("unit", {}).get("code", "K")
                if weight_unit.upper() in ["K", "KG", "KGS"]:
                    weight_unit = "kg"
                
                weight = None
                if weight_val is not None:
                    weight = {"value": float(weight_val), "unit": weight_unit}
                
                events = []
                milestones = item.get("fulfillmentInfo", {}).get("serviceInfo", {}).get("milestone", [])
                
                for m in milestones:
                    code_obj = m.get("code", {})
                    code = code_obj.get("code", "")
                    description = code_obj.get("description", "")
                    
                    station = m.get("station", {}).get("code", "")
                    
                    event_time = m.get("statusDate", {}).get("achieved", "")
                    # The achieved time looks like "2026-08-07 20:09:00"
                    
                    # Flight Info
                    flight = ""
                    status_data = m.get("statusData", {})
                    transport_info = status_data.get("itinerary", {}).get("transportInfo", {})
                    if transport_info:
                        carrier = transport_info.get("carrier", "")
                        fnum = transport_info.get("number", "")
                        if carrier and fnum:
                            flight = f"{carrier}{fnum}"
                    
                    evt_qty = status_data.get("quantity", {})
                    evt_pieces = evt_qty.get("piece")
                    evt_weight_val = evt_qty.get("weight", {}).get("value")
                    
                    final_pieces = evt_pieces if evt_pieces is not None else total_pieces
                    final_weight = float(evt_weight_val) if evt_weight_val is not None else (weight_val if weight_val is not None else None)
                    
                    # Add standard status message
                    status_message = description if description else code
                    
                    events.append({
                        "station": station,
                        "status_code": code,
                        "status_message": status_message,
                        "event_time": event_time,
                        "milestone_status": f"{code} - {description}" if description else code,
                        "raw_status": code,
                        "flight_info": flight,
                        "pieces": final_pieces,
                        "weight": final_weight
                    })
                
                # Sort events chronologically by event_time
                events.sort(key=lambda x: x["event_time"] or "")
                
                overall_status = "In Transit"
                latest_event = events[-1] if events else None
                if latest_event:
                    overall_status = latest_event.get("status_code", "In Transit")
                
                return ProviderResult(
                    success=True,
                    provider_name=self.name,
                    status_code=200,
                    status=overall_status,
                    origin=origin,
                    destination=dest,
                    pieces=total_pieces,
                    weight=weight,
                    events=events,
                    latest_event=latest_event,
                    raw_data=details_data,
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Virgin Atlantic Cargo tracking request timed out.",
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
            logger.error(f"Virgin Atlantic Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
