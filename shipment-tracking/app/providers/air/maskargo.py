import urllib.request
import urllib.error
import json
import logging
import time
import asyncio
from typing import Optional

from app.providers.base import BaseProvider, ProviderResult
from app.schemas.tracking import UnifiedTrackingEvent

logger = logging.getLogger("shipment_tracking.providers.maskargo")

class MasKargoProvider(BaseProvider):
    """
    Live provider for MASkargo (Malaysia Airlines) - 232.
    Uses urllib to bypass Cloudflare TLS fingerprinting blocks that catch httpx.
    """

    name = "maskargo"
    mode = "AIR"

    def _fetch_sync(self, awb: str) -> tuple[int, str]:
        url = f"https://www.maskargo.com/bin/mh/revamp/maskargo/shipment/tracking?awbShipmentTrackingNumber={awb}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': f'https://www.maskargo.com/en/shipment-tracking.html?prefixNumber={awb[:3]}&awbNumber={awb[3:]}'
        })
        
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.status, response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            return e.code, str(e.read())
        except urllib.error.URLError as e:
            return 500, str(e.reason)
        except Exception as e:
            return 500, str(e)

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        
        awb = f"{prefix}{serial}"
        
        try:
            logger.info(f"MasKargo: Fetching tracking data for {awb}...")
            # Run urllib blocking request in thread pool
            status_code, body = await asyncio.to_thread(self._fetch_sync, awb)
            
            latency = round((time.time() - start_time) * 1000, 2)
            
            if status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=status_code,
                    error=f"HTTP Error: {body}",
                    latency_ms=latency,
                )

            data = json.loads(body)
            if not data or "data" not in data or not data["data"]:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"No tracking data found for AWB {awb}.",
                    latency_ms=latency,
                )

            return self._parse_json(data["data"], prefix, serial, latency)

        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"MasKargo unexpected error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    def _parse_json(self, data: dict, prefix: str, serial: str, latency: float) -> ProviderResult:
        events = []
        
        history = data.get("history", [])
        
        for ev in history:
            station = ev.get("station")
            code = ev.get("status")
            desc = ev.get("description")
            dt_str = ev.get("timestamp")
            
            # e.g., 2026-09-19 08:15:00
            iso_dt = None
            if dt_str:
                iso_dt = dt_str.replace(" ", "T")
                
            flight = ev.get("flight", {}).get("flightNumber")
            
            ev_pieces = ev.get("pieces")
            
            ev_weight_raw = ev.get("weight")
            ev_weight = None
            if isinstance(ev_weight_raw, dict):
                ev_weight = ev_weight_raw.get("value")
            elif isinstance(ev_weight_raw, (int, float, str)):
                try:
                    ev_weight = float(ev_weight_raw)
                except ValueError:
                    pass
            
            events.append({
                "station": station,
                "status_code": code[:3].upper() if code else "UNK",
                "status_message": desc,
                "event_time": iso_dt or dt_str,
                "flight_info": flight,
                "pieces": ev_pieces,
                "weight": ev_weight,
                "milestone_status": f"{code} - {desc}",
                "raw_status": desc
            })

        latest_event = events[-1] if events else None

        routing = data.get("routing", {})
        origin_code = routing.get("origin", {}).get("stationCode")
        dest_code = routing.get("destStation", {}).get("stationCode")

        pieces = data.get("pieces")
        weight = data.get("weight")

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=data.get("status", "Unknown"),
            origin=origin_code,
            destination=dest_code,
            pieces=pieces,
            weight=weight,
            events=events,
            latest_event=latest_event,
            raw_data={
                "carrier": "Malaysia Airlines",
                "awb": f"{prefix}-{serial}",
            },
            latency_ms=latency,
        )
