import time
import httpx
import re
from datetime import datetime
from typing import Dict, Any

from app.providers.base import BaseProvider, ProviderResult
import logging

logger = logging.getLogger("shipment_tracking.providers.aeroflot_cargo")

class AeroflotCargoProvider(BaseProvider):
    name = "aeroflot_cargo"

    def _map_status_code(self, milestone: str) -> str:
        ms = milestone.lower()
        if "прибытие" in ms or "принят" in ms:
            return "Rcf" 
        if "выдач" in ms or "выдан" in ms:
            return "Dlv"
        if "отправлен" in ms or "убыл" in ms:
            return "Dep"
        if "заявлен" in ms:
            return "Bkd"
        return ""

    async def track(self, tracking_number: str, prefix: str = "", serial: str = "", **kwargs) -> ProviderResult:
        start_time = time.time()
        base_url = "https://www.moscow-cargo.com/index.php/en/"
        api_url = "https://www.moscow-cargo.com/intapi/statusawb_v8"
        
        try:
            logger.info(f"Aeroflot Cargo: Tracking {prefix}-{serial}...")
            
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                # 1. Fetch CSRF token from homepage
                r1 = await client.get(base_url)
                r1.raise_for_status()
                
                token_match = re.search(r'name="_token".*?value="([^"]+)"', r1.text)
                if not token_match:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=500,
                        error="Could not extract CSRF token from Aeroflot (Moscow Cargo) portal.",
                        latency_ms=round((time.time() - start_time) * 1000, 2)
                    )
                
                csrf_token = token_match.group(1)
                
                # 2. Query tracking API
                payload = {
                    "_token": csrf_token,
                    "num": f"{prefix}-{serial}",
                    "technology": "",
                    "id": "",
                    "type": "awb",
                    "version": "7.7"
                }
                
                r2 = await client.post(api_url, data=payload)
                r2.raise_for_status()
                
                data = r2.json()
                
                if data.get("errorcode") != 0 or not data.get("data"):
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error=f"No data found for {prefix}-{serial} on Aeroflot Cargo.",
                        latency_ms=round((time.time() - start_time) * 1000, 2)
                    )
                    
                cargo_data = data["data"]
                awbinfo = cargo_data.get("awbinfo", {})
                
                origin = awbinfo.get("origin")
                dest = awbinfo.get("destination")
                
                pieces = None
                if awbinfo.get("pieces"):
                    pieces = int(awbinfo.get("pieces"))
                    
                weight = None
                if awbinfo.get("charge_weight"):
                    weight = {"value": float(awbinfo.get("charge_weight")), "unit": "kg"}
                    
                events = []
                for event in cargo_data.get("status", []):
                    date_str = event.get("createdate", "")
                    text = event.get("text", "")
                    flight = event.get("flight_num", "")
                    
                    status_code = self._map_status_code(text)
                    
                    iso_date = ""
                    if date_str:
                        try:
                            parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                            iso_date = parsed_date.isoformat()
                        except ValueError:
                            iso_date = date_str
                            
                    msg = f"{text} (Flight: {flight})" if flight else text
                            
                    events.append({
                        "station": dest if "выдан" in text.lower() or "прибытие" in text.lower() else origin,
                        "status_code": status_code,
                        "status_message": msg,
                        "event_time": iso_date,
                        "milestone_status": f"{status_code} - {msg}" if status_code else msg,
                        "raw_status": text
                    })
                    
                latest_event = events[-1] if events else None
                overall_status = "In Transit"
                if latest_event:
                    overall_status = latest_event.get("status_message", "In Transit")
                    
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
                    raw_data={"url": api_url},
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Aeroflot tracking request timed out.",
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
            logger.error(f"Aeroflot Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
