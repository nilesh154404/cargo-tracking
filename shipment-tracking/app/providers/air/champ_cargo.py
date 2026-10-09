import time
import logging
import json
from typing import Optional
from datetime import datetime

import httpx

from app.providers.base import BaseProvider, ProviderResult
from app.schemas.tracking import UnifiedTrackingEvent

logger = logging.getLogger("shipment_tracking.providers.champ_cargo")


class ChampCargoProvider(BaseProvider):
    """
    Live provider for CHAMP Cargosystems powered airlines (e.g. Gulf Air - 072).
    Uses the API at freight.aero / ebooking.champ.aero.
    """

    name = "champ_cargo"
    mode = "AIR"

    # Mapping of prefix to carrierId for CHAMP's API
    # 072: GF (Gulf Air)
    PREFIX_TO_CARRIER = {
        "072": "GF",
    }

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        
        awb = f"{prefix}-{serial}"
        carrier_id = self.PREFIX_TO_CARRIER.get(prefix, "")

        url = "https://www.freight.aero/tracking_service.asp?is_portlet=1"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": "https://www.freight.aero",
            "Referer": "https://www.freight.aero/tracking.asp",
        }

        payload = {
            "portalId": "CHA", 
            "awbInfo": [{"awbNumber": awb, "carrierId": carrier_id, "trackingAirline": ""}],
            "captchaResponse": "FREIGHT_LOGGED_CAPTCHA"
        }

        try:
            logger.info(f"ChampCargo: Fetching tracking data for {awb}...")
            async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            data = response.json()
            latency = round((time.time() - start_time) * 1000, 2)

            if not data or not isinstance(data, list) or len(data) == 0:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"No tracking data found for AWB {awb}.",
                    latency_ms=latency,
                )

            return self._parse_json(data[0], prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="ChampCargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"ChampCargo HTTP error: {exc}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code,
                error=f"HTTP Error: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"ChampCargo unexpected error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    def _parse_json(self, data: dict, prefix: str, serial: str, latency: float) -> ProviderResult:
        if data.get("responseCode") != "OK":
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=404,
                status="NOT_FOUND",
                error=f"Error from CHAMP Cargo: {data.get('responseCode')}",
                latency_ms=latency,
            )

        events_data = data.get("events", [])
        events = []

        # Parse overall pieces and weight
        pieces = data.get("totalPieces")
        try:
            pieces = int(pieces) if pieces is not None else None
        except ValueError:
            pieces = None

        weight_val = None
        weight_unit = None
        raw_weight = data.get("weight", "")
        if raw_weight:
            parts = raw_weight.split()
            if len(parts) >= 2:
                try:
                    weight_val = float(parts[0])
                    weight_unit = parts[1].lower()
                except ValueError:
                    pass

        # Sort events by sequence number descending so newest is first (standard mapping is newest last, so we'll reverse after)
        events_data.sort(key=lambda x: x.get("eventSequenceNumber", 0))

        for ev in events_data:
            dt_str = ev.get("eventTime", "") # e.g. "25-Sep-2026 09:00"
            iso_dt = None
            if dt_str:
                try:
                    # Parse "25-Sep-2026 09:00"
                    dt_obj = datetime.strptime(dt_str.strip(), "%d-%b-%Y %H:%M")
                    iso_dt = dt_obj.isoformat()
                except ValueError:
                    pass

            status_str = ev.get("status", "")
            code = status_str # CHAMP gives full strings like "Received from shipper"
            
            flight = ev.get("flightNumber", "")
            
            # They don't provide event-level pieces/weight explicitly in clean fields, but it's in the detail text
            # e.g. "Total shipment of 1 piece at 25.0 KG booked"
            import re
            detail = ev.get("detail", "")
            # Clean HTML from detail
            clean_detail = re.sub(r'<[^>]+>', '', detail)
            
            ev_pieces = None
            pm = re.search(r"(\d+)\s+piece", clean_detail, re.IGNORECASE)
            if pm:
                ev_pieces = int(pm.group(1))

            events.append({
                "station": "",
                "status_code": code[:3].upper() if code else "UNK",
                "status_message": code,
                "event_time": iso_dt or dt_str,
                "flight_info": flight if flight else None,
                "pieces": ev_pieces,
                "weight": None,
                "milestone_status": f"{code} - {clean_detail}",
                "raw_status": clean_detail
            })

        # We need events to be chronological (oldest first). We sorted by sequence ascending.
        # But wait! Unified format standard in the system implies oldest to newest, so ascending is good.
        latest_event = events[-1] if events else None
        
        # Origin and destination are like "Chennai Madras Meenambakkam (MAA)"
        origin_raw = data.get("origin", "")
        dest_raw = data.get("destination", "")
        
        def extract_code(location: str):
            m = re.search(r"\(([A-Z]{3})\)", location)
            return m.group(1) if m else location

        origin = extract_code(origin_raw)
        destination = extract_code(dest_raw)

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=data.get("status", "Unknown"),
            origin=origin,
            destination=destination,
            pieces=pieces,
            weight={"value": weight_val, "unit": weight_unit} if weight_val else None,
            events=events,
            latest_event=latest_event,
            raw_data={
                "carrier": data.get("carrier"),
                "awb": data.get("awbNumber"),
            },
            latency_ms=latency,
        )
