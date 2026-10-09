import time
import logging
from typing import Optional
import httpx
from datetime import datetime

from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.etihad")

class EtihadCargoProvider(BaseProvider):
    """
    Live provider for Etihad Cargo (Prefix 607).
    Uses the internal ADA services API.
    """

    name = "etihad_cargo"
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
        
        url = "https://www.etihadcargo.com/ada-services/eycargo-trackntrace/v1/track-and-trace"

        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://www.etihadcargo.com",
            "referer": "https://www.etihadcargo.com/en/e-services/shipment-tracking"
        }
        
        payload = {
            "shipmentPrefix": prefix,
            "masterDocumentNumber": serial,
            "language": "en"
        }

        try:
            logger.info(f"EtihadCargo: Fetching tracking data for {prefix}-{serial}...")
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
            data = response.json()
            latency = round((time.time() - start_time) * 1000, 2)
            
            return self._parse_json(data, prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Etihad Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"EtihadCargo HTTP error: {exc}")
            
            # 404 is commonly returned if the shipment doesn't exist
            if exc.response.status_code == 404:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    status="NOT_FOUND",
                    error=f"Tracking data not found for AWB {prefix}-{serial}.",
                    latency_ms=latency,
                )
            
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code,
                error=f"HTTP Error: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"EtihadCargo unexpected error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    def _parse_json(self, data: dict, prefix: str, serial: str, latency: float) -> ProviderResult:
        """Parse the JSON response from Etihad."""
        
        # Check if the response contains the expected structure
        response_data = data.get("response")
        if not response_data:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=404,
                status="NOT_FOUND",
                error=f"Tracking data not found for AWB {prefix}-{serial}.",
                latency_ms=latency,
            )
            
        awb_data = response_data.get("awb", {})
        if not awb_data:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=404,
                status="NOT_FOUND",
                error=f"No AWB data found for {prefix}-{serial}.",
                latency_ms=latency,
            )

        events = []
        
        # Parse segments (events)
        segments = awb_data.get("segments", {}).get("segment", [])
        if isinstance(segments, dict):
            # Sometimes single items are returned as objects instead of arrays in poor XML-to-JSON
            segments = [segments]
            
        for seg in segments:
            status_code = seg.get("status", "")
            status_message = seg.get("statusCode", "")
            event_date = seg.get("eventDate", "")  # e.g., 30-Aug-2026
            event_time = seg.get("eventTime", "")  # e.g., 21:58
            
            # Reconstruct datetime string
            iso_dt = None
            if event_date and event_time:
                iso_dt = self._parse_datetime(f"{event_date} {event_time}")
            elif event_date:
                iso_dt = self._parse_datetime(event_date)
            
            station = seg.get("airportCode") or seg.get("origin") or seg.get("dest", "")
            flight_num = seg.get("flightNum", "")
            pieces = seg.get("numPieces", "")
            weight = seg.get("weight", "")
            
            # Build raw_status
            raw_details = []
            if flight_num: raw_details.append(f"Flight: {flight_num}")
            if pieces: raw_details.append(f"Pieces: {pieces}")
            if weight: raw_details.append(f"Weight: {weight}")
            
            events.append({
                "station": station,
                "status_code": status_code,
                "status_message": status_message,
                "event_time": iso_dt or f"{event_date} {event_time}".strip(),
                "milestone_status": f"{status_code} - {status_message}",
                "raw_status": ", ".join(raw_details) if raw_details else ""
            })

        # The JSON has latest events first, so we reverse to chronological
        events.reverse()
        
        # Extract summary info
        origin = awb_data.get("origin")
        destination = awb_data.get("destination")
        
        pieces_val = awb_data.get("pieces")
        weight_val = awb_data.get("weight")
        volume_val = awb_data.get("volume")
        
        unit_measurements = awb_data.get("unitMeasurements", {})
        weight_unit = unit_measurements.get("weightUnit", "K")
        if weight_unit == "K":
            weight_unit = "kg"
        elif weight_unit == "L":
            weight_unit = "lb"

        # Determine overall status
        latest_event = events[-1] if events else None
        
        # E.g. "NFD"
        latest_status_code = awb_data.get("latestStatus")
        overall_status = self._map_status_code(latest_status_code) if latest_status_code else "Unknown"

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=overall_status,
            origin=origin,
            destination=destination,
            pieces=int(pieces_val) if pieces_val and pieces_val.isdigit() else None,
            weight={"value": float(weight_val), "unit": weight_unit} if weight_val else None,
            volume=float(volume_val) if volume_val else None,
            events=events,
            latest_event=latest_event,
            raw_data={
                "carrier": "Etihad Cargo",
                "awb": f"{prefix}-{serial}",
                "routing": awb_data.get("routing"),
                "latestStatusDescription": awb_data.get("latestStatusDescription")
            },
            latency_ms=latency,
        )

    def _map_status_code(self, code: str) -> str:
        """Map standard IATA codes to broad status strings."""
        if not code:
            return "Unknown"
        code = code.upper()
        if code in ("DLV", "DEL"):
            return "Delivered"
        elif code in ("ARR", "RCF", "NFD", "AWD"):
            return "Arrived"
        elif code in ("DEP", "MAN", "FFM"):
            return "In Transit"
        elif code in ("RCS", "BKD", "BKG", "FOH"):
            return "Accepted"
        elif code in ("DIS", "CRC"):
            return "Exception/Hold"
        return "Unknown"

    def _parse_datetime(self, dt_str: str) -> Optional[str]:
        """
        Parse: '30-Aug-2026 21:58' -> ISO 8601
        or '30-Aug-2026' -> ISO 8601
        """
        try:
            if ":" in dt_str:
                dt_obj = datetime.strptime(dt_str.strip(), "%d-%b-%Y %H:%M")
            else:
                dt_obj = datetime.strptime(dt_str.strip(), "%d-%b-%Y")
            return dt_obj.isoformat()
        except ValueError:
            return None
