import time
import logging
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.dhl_aviation")

class DHLAviationCargoProvider(BaseProvider):
    """
    Live provider for DHL Aviation Cargo (Prefix 615).
    Uses the public tracking page at aviationcargo.dhl.com.
    """

    name = "dhl_aviation_cargo"
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
        
        # DHL Aviation uses the full 11-digit AWB without hyphen for the URL
        awb = f"{prefix}{serial}"
        url = f"https://aviationcargo.dhl.com/track/{awb}"

        headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.5",
            "upgrade-insecure-requests": "1",
        }

        try:
            logger.info(f"DHLAviation: Fetching tracking page for {prefix}-{serial}...")
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            html = response.text
            latency = round((time.time() - start_time) * 1000, 2)

            return self._parse_html(html, prefix, serial, latency)

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="DHL Aviation Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"DHLAviation HTTP error: {exc}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=exc.response.status_code,
                error=f"HTTP Error: {exc}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"DHLAviation unexpected error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    def _parse_html(self, html: str, prefix: str, serial: str, latency: float) -> ProviderResult:
        """Parse the HTML response from aviationcargo.dhl.com"""
        soup = BeautifulSoup(html, 'html.parser')

        # Check if tracking data is present
        tracking_table = soup.find('table', class_='tracking-results')
        if not tracking_table:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=404,
                status="NOT_FOUND",
                error=f"No tracking data found for AWB {prefix}-{serial} on DHL Aviation Cargo.",
                latency_ms=latency,
            )

        events = []
        current_date = None

        # Parse events
        for row in tracking_table.find_all('tr'):
            th = row.find('th')
            if th and 'colspan' in th.attrs and th.attrs['colspan'] == '2':
                # E.g. "Tuesday, September 1, 2026"
                current_date = th.get_text(strip=True)
                continue
                
            tds = row.find_all('td')
            if len(tds) >= 6:
                code = tds[0].get_text(strip=True)
                desc = tds[1].get_text(strip=True)
                qty = tds[2].get_text(strip=True)
                loc = tds[3].get_text(strip=True)
                facility = tds[4].get_text(strip=True)
                time_str = tds[5].get_text(strip=True)
                
                dt_str = f"{current_date} {time_str}" if current_date else time_str
                iso_dt = self._parse_datetime(dt_str)
                
                import re
                
                # Parse pieces from qty, e.g., "1 pcs" -> 1
                ev_pieces = None
                qty_clean = qty.lower().replace("pcs", "").strip()
                if qty_clean.isdigit():
                    ev_pieces = int(qty_clean)
                
                # Parse flight info from desc, e.g., "Manifested onto movement D0591 to DEL"
                flight_m = re.search(r"(?:movement|flight)\s+([A-Z0-9]+)", desc, re.IGNORECASE)
                ev_flight = flight_m.group(1) if flight_m else None

                events.append({
                    "station": loc,
                    "status_code": code,
                    "status_message": desc,
                    "event_time": iso_dt or dt_str,
                    "pieces": ev_pieces,
                    "flight_info": ev_flight,
                    "milestone_status": f"{code} - {desc}",
                    "raw_status": f"Facility: {facility}, Qty: {qty}"
                })

        # Reverse events if they are chronological (DHL usually puts newest first)
        # We want the standard order to be oldest first or just pass as parsed
        # Actually DHL HTML has newest first (e.g. Sept 1, then Aug 31). We should reverse to chronological.
        events.reverse()

        # Parse summary info
        origin = None
        destination = None
        pieces = None
        weight_val = None
        weight_unit = None
        overall_status = "Unknown"
        
        # Try to parse summary text like: "These are the tracking results for 61567903813 for 41 pieces @ 2354 KG as X."
        summary_node = soup.find(string=lambda t: t and "These are the tracking results for" in t)
        if summary_node:
            text = summary_node.parent.get_text(strip=True)
            # E.g. "These are the tracking results for 61567903813 for 41 pieces @ 2354 KG as X."
            import re
            m = re.search(r"for\s*(\d+)\s*pieces\s*@\s*([\d\.]+)\s*(KG|LB)", text, re.IGNORECASE)
            if m:
                pieces = m.group(1)
                weight_val = float(m.group(2))
                weight_unit = m.group(3).lower()
        
        # Try to parse Origin and Destination from the text
        org_dest_nodes = soup.find_all(string=lambda t: t and "From DHL Org" in t)
        for node in org_dest_nodes:
            text = node.parent.get_text(strip=True)
            # "From DHL Org FRA to DHL Dest DEL." or "From DHL OrgFRAto DHL DestDEL."
            m = re.search(r"From DHL Org\s*([A-Z]{3})\s*to DHL Dest\s*([A-Z]{3})", text, re.IGNORECASE)
            if m:
                origin = m.group(1)
                destination = m.group(2)
                break

        # Check the status box
        summary_table = soup.find('table', class_='tracking-summary')
        if summary_table:
            status_row = summary_table.find('tr', class_='last-row')
            if status_row:
                status_td = status_row.find('td', class_='status-container')
                if status_td:
                    raw_status = status_td.get_text(strip=True)
                    # raw_status might be "DLV - Delivery"
                    if "-" in raw_status:
                        code = raw_status.split("-")[0].strip()
                        overall_status = self._map_status_code(code)
                    else:
                        overall_status = raw_status

        latest_event = events[-1] if events else None

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=overall_status,
            origin=origin,
            destination=destination,
            pieces=int(pieces) if pieces else None,
            weight={"value": weight_val, "unit": weight_unit} if weight_val else None,
            events=events,
            latest_event=latest_event,
            raw_data={
                "carrier": "DHL Aviation Cargo",
                "awb": f"{prefix}-{serial}",
            },
            latency_ms=latency,
        )

    def _map_status_code(self, code: str) -> str:
        """Map standard DHL/IATA codes to broad status strings."""
        code = code.upper()
        if code in ("DLV", "DEL"):
            return "Delivered"
        elif code in ("ARR", "RCF"):
            return "Arrived"
        elif code in ("DEP", "MAN", "FFM"):
            return "In Transit"
        elif code in ("RCS", "BKD", "BKG"):
            return "Accepted"
        elif code in ("DIS", "NFD", "AWD"):
            return "Exception/Hold"
        return "Unknown"

    def _parse_datetime(self, dt_str: str) -> Optional[str]:
        """
        Parse: 'Tuesday, September 1, 2026 00:33' -> ISO 8601
        """
        try:
            # The format is "%A, %B %d, %Y %H:%M"
            # e.g. "Tuesday, September 1, 2026 00:33"
            dt_obj = datetime.strptime(dt_str.strip(), "%A, %B %d, %Y %H:%M")
            return dt_obj.isoformat()
        except ValueError:
            return None
