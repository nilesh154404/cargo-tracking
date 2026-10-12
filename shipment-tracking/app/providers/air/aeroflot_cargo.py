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

    async def track(
        self,
        prefix: str = "",
        serial: str = "",
        tracking_number: str = "",
        language: str = "en-us",
        force_refresh: bool = False,
        **kwargs,
    ) -> ProviderResult:
        if not prefix or not serial:
            if tracking_number and "-" in tracking_number:
                prefix, serial = tracking_number.split("-", 1)
            elif tracking_number and len(tracking_number) >= 11:
                prefix, serial = tracking_number[:3], tracking_number[3:]

        start_time = time.time()
        curl_cmd = None
        response_text = None
        base_url = "https://www.moscow-cargo.com/index.php/en/"
        api_url = "https://www.moscow-cargo.com/intapi/statusawb_v8"
        
        try:
            logger.info(f"Aeroflot Cargo: Tracking {prefix}-{serial}...")
            
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                # 1. Fetch CSRF token from homepage
                curl_cmd = self.build_curl_command("GET", base_url)
                r1 = await client.get(base_url)
                r1.raise_for_status()
                response_text = r1.text
                
                token_match = re.search(r'name="_token".*?value="([^"]+)"', r1.text)
                if not token_match:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=500,
                        error="Could not extract CSRF token from Aeroflot (Moscow Cargo) portal.",
                        latency_ms=round((time.time() - start_time) * 1000, 2),
                        request_curl=curl_cmd,
                        response_body=response_text,
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
                
                curl_cmd = self.build_curl_command("POST", api_url, body=payload)
                r2 = await client.post(api_url, data=payload)
                r2.raise_for_status()
                response_text = r2.text
                
                data = r2.json()
                
                if data.get("errorcode") != 0 or not data.get("data"):
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error=f"No data found for {prefix}-{serial} on Aeroflot Cargo.",
                        latency_ms=round((time.time() - start_time) * 1000, 2),
                        request_curl=curl_cmd,
                        response_body=response_text,
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
                    latency_ms=round((time.time() - start_time) * 1000, 2),
                    request_curl=curl_cmd,
                    response_body=response_text,
                )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Aeroflot tracking request timed out.",
                latency_ms=round((time.time() - start_time) * 1000, 2),
                request_curl=curl_cmd,
                response_body=response_text,
            )
        except httpx.HTTPStatusError as exc:
            resp_body = exc.response.text if hasattr(exc, "response") else response_text
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code if hasattr(exc, "response") else 500,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2),
                request_curl=curl_cmd,
                response_body=resp_body,
            )
        except Exception as exc:
            logger.error(f"Aeroflot Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2),
                request_curl=curl_cmd,
                response_body=response_text,
            )
