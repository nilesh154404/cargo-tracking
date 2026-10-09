import time
import logging
from typing import Optional
import httpx
from datetime import datetime

from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.kuwait")

class KuwaitAirwaysProvider(BaseProvider):
    """
    Live provider for Kuwait Airways (Prefix 229).
    Uses the internal cargo API.
    """

    name = "kuwait_airways"
    mode = "AIR"

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        
        url = f"https://services.kuwaitairways.com/cargo/api/GetCargoInfo/{prefix}/{serial}/en"

        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "accept": "application/json, text/plain, */*",
            "origin": "https://kuwaitairways.com",
            "referer": "https://kuwaitairways.com/"
        }
        
        try:
            logger.info(f"KuwaitAirways: Fetching tracking data for {prefix}-{serial}...")
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            data = response.json()
            latency = int((time.time() - start_time) * 1000)
            
            if data.get("responseCode") != "1" and not data.get("segments"):
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=data.get("responseText") or "Tracking not found",
                    latency_ms=latency
                )

            origin = data.get("origin")
            destination = data.get("destination")
            pieces_val = data.get("pieces")
            weight_val = data.get("weight")
            volume_val = data.get("volume")

            events = []
            
            raw_segments = data.get("segments", [])
            raw_segments = sorted(raw_segments, key=lambda x: x.get("sequenceNo", 0))

            for seg in raw_segments:
                date_str = seg.get("eventDate", "")
                time_str = seg.get("eventTime", "")
                dt_obj = self._parse_datetime(f"{date_str} {time_str}")
                
                status_msg = seg.get("status") or seg.get("statusMessage")
                location = seg.get("flightAirPort")
                flight = seg.get("flightNum")
                seg_pieces = seg.get("numPieces")
                seg_weight = seg.get("weight")
                status_code = seg.get("statusCode", "")
                
                raw_details = []
                if flight: raw_details.append(f"Flight: {flight}")
                if seg_pieces: raw_details.append(f"Pieces: {seg_pieces}")
                if seg_weight: raw_details.append(f"Weight: {seg_weight}")
                
                events.append({
                    "station": location,
                    "status_code": status_code,
                    "status_message": status_msg,
                    "event_time": dt_obj or f"{date_str} {time_str}".strip(),
                    "milestone_status": f"{status_code} - {status_msg}" if status_code else str(status_msg),
                    "raw_status": ", ".join(raw_details) if raw_details else ""
                })

            events.reverse()
            
            latest_event = events[-1] if events else None
            
            latest_status_code = raw_segments[-1].get("statusCode") if raw_segments else None
            overall_status = self._map_status_code(latest_status_code) if latest_status_code else "Unknown"

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=overall_status,
                origin=origin,
                destination=destination,
                pieces=int(pieces_val) if pieces_val and str(pieces_val).isdigit() else None,
                weight={"value": float(weight_val), "unit": "kg"} if weight_val else None,
                volume=float(volume_val) if volume_val else None,
                events=events,
                latest_event=latest_event,
                raw_data=data,
                latency_ms=latency
            )

        except httpx.HTTPError as e:
            logger.error(f"KuwaitAirways HTTP Error: {e}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"HTTP Error: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            logger.error(f"KuwaitAirways Parsing Error: {e}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Parsing Error: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000)
            )

    def _map_status_code(self, code: str) -> str:
        if not code:
            return "Unknown"
        code = code.upper()
        if code in ("DLV", "DEL"):
            return "Delivered"
        elif code in ("ARR", "RCF", "NFD", "AWD"):
            return "Arrived"
        elif code in ("DEP", "MAN", "FFM"):
            return "In Transit"
        elif code in ("RCS", "BKD", "BKG", "FOH", "PRE"):
            return "Accepted"
        elif code in ("DIS", "CRC"):
            return "Exception/Hold"
        return "Unknown"

    def _parse_datetime(self, dt_str: str) -> Optional[str]:
        try:
            dt_obj = datetime.strptime(dt_str.strip(), "%d-%b-%y %H:%M")
            return dt_obj.isoformat()
        except ValueError:
            pass
        
        try:
            dt_obj = datetime.strptime(dt_str.strip(), "%d-%b-%Y %H:%M")
            return dt_obj.isoformat()
        except ValueError:
            return None
