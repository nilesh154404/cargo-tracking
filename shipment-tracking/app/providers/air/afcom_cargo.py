import re
from typing import Dict, Any, List
import httpx
from bs4 import BeautifulSoup
import time
from datetime import datetime
from app.providers.base import BaseProvider, ProviderResult
import logging

logger = logging.getLogger(__name__)


class AfcomCargoProvider(BaseProvider):
    """
    Tracking provider for Afcom Cargo (198).
    Uses ASP.NET WebForms endpoints which requires extracting __VIEWSTATE
    and __VIEWSTATEGENERATOR from a GET request, before POSTing the payload.
    """
    name = "afcom_cargo"
    mode = "AIR"

    def __init__(self):
        super().__init__()
        self.url = "https://booking.afcomcargo.com/FrmAWBTracking.aspx"

    async def track(self, tracking_number: str, prefix: str = "", serial: str = "", **kwargs) -> ProviderResult:
        """
        Fetch tracking data for Afcom Cargo.
        """
        start_time = time.time()
        async with httpx.AsyncClient(verify=False) as client:
            try:
                awb = serial
                # Step 1: GET request to retrieve ASP.NET hidden fields
                logger.info(f"[AfcomCargo] Fetching initial page for {prefix}-{awb}")
                get_response = await client.get(self.url)
                get_response.raise_for_status()

                soup = BeautifulSoup(get_response.text, 'html.parser')
                viewstate = soup.find('input', id='__VIEWSTATE')
                viewstate_generator = soup.find('input', id='__VIEWSTATEGENERATOR')
                event_validation = soup.find('input', id='__EVENTVALIDATION')

                viewstate_val = viewstate['value'] if viewstate else ''
                viewstate_gen_val = viewstate_generator['value'] if viewstate_generator else ''
                event_val = event_validation['value'] if event_validation else ''

                # Step 2: POST request with AWB details
                data = {
                    'ToolkitScriptManager1_HiddenField': '',
                    '__EVENTTARGET': '',
                    '__EVENTARGUMENT': '',
                    '__VIEWSTATE': viewstate_val,
                    '__VIEWSTATEGENERATOR': viewstate_gen_val,
                    '__VIEWSTATEENCRYPTED': '',
                    'txtPrefix': prefix,
                    'TextBoxAWBno': awb,
                    'ButtonGO': 'Track',
                    'hdnIsAlaska': 'false'
                }

                if event_val:
                    data['__EVENTVALIDATION'] = event_val

                logger.info(f"[AfcomCargo] Submitting POST for {prefix}-{awb}")
                post_response = await client.post(self.url, data=data)
                post_response.raise_for_status()

                # Parse the returned HTML
                post_soup = BeautifulSoup(post_response.text, 'html.parser')
                
                awb_no_elem = post_soup.find('span', id='lblAWBNo')
                if not awb_no_elem:
                    logger.warning(f"[AfcomCargo] Tracking not found for {prefix}-{awb}")
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error="AWB not found or no data available",
                        events=[],
                        latest_event=None,
                        raw_data={"source": "Afcom Cargo"},
                        latency_ms=round((time.time() - start_time) * 1000, 2)
                    )

                origin_elem = post_soup.find('span', id='lblOrigin')
                dest_elem = post_soup.find('span', id='lblDestination')

                origin = origin_elem.text.strip() if origin_elem else ""
                dest = dest_elem.text.strip() if dest_elem else ""
                
                events = self._parse_history(post_soup)
                
                status_mapped = "IN_TRANSIT"
                if events:
                    status_mapped = events[-1]["status_code"]
                    
                latest_event = events[-1] if events else None
                total_pieces = latest_event.get("pieces") if latest_event else None
                total_weight = latest_event.get("weight") if latest_event else None

                return ProviderResult(
                    success=True,
                    provider_name=self.name,
                    status_code=200,
                    status=status_mapped,
                    error=None,
                    origin=origin,
                    destination=dest,
                    pieces=total_pieces,
                    weight=total_weight,
                    events=events,
                    latest_event=latest_event,
                    raw_data={"source": "Afcom Cargo"},
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )

            except httpx.HTTPError as e:
                logger.error(f"[AfcomCargo] HTTP error for {prefix}-{awb}: {str(e)}")
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=500,
                    status="HTTP_ERROR",
                    error=str(e),
                    events=[],
                    latest_event=None,
                    raw_data={"source": "Afcom Cargo"},
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )
            except Exception as e:
                logger.error(f"[AfcomCargo] Error tracking {prefix}-{awb}: {str(e)}")
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=500,
                    status="INTERNAL_ERROR",
                    error=str(e),
                    events=[],
                    latest_event=None,
                    raw_data={"source": "Afcom Cargo"},
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )

    def _parse_history(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        history = []
        status_table = soup.find('table', id='GridViewAwbTracking')
        
        if not status_table:
            return history

        # Skip the header row
        rows = status_table.find_all('tr')[1:]
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 10:
                station = cols[0].text.strip()
                milestone = cols[1].text.strip()
                pieces = cols[2].text.strip()
                weight = cols[3].text.strip()
                flight = cols[4].text.strip()
                event_date = cols[9].text.strip()

                pieces_parsed = None
                weight_parsed = None
                if pieces:
                    pc_match = re.search(r"[\d\.]+", pieces)
                    pieces_parsed = int(float(pc_match.group())) if pc_match else None
                if weight:
                    wt_match = re.search(r"[\d\.]+", weight)
                    weight_parsed = float(wt_match.group()) if wt_match else None

                event_date_iso = event_date
                if event_date:
                    try:
                        # e.g. "29/07/2026 22:13:10"
                        parsed_date = datetime.strptime(event_date, "%d/%m/%Y %H:%M:%S")
                        event_date_iso = parsed_date.isoformat()
                    except ValueError:
                        pass

                desc = f"{milestone} at {station}"
                if flight:
                    desc += f" (Flight {flight})"
                if pieces or weight:
                    desc += f" [Pcs: {pieces}, Wt: {weight}]"

                # Use a basic mapping for statuses. Could be expanded based on seen milestones.
                status_code = "IN_TRANSIT"
                milestone_upper = milestone.upper()
                if "DELIVER" in milestone_upper:
                    status_code = "DELIVERED"
                elif "ARRIV" in milestone_upper:
                    status_code = "ARRIVED"
                elif "DEPART" in milestone_upper:
                    status_code = "DEPARTED"

                history.append({
                    "event_time": event_date_iso,
                    "station": station,
                    "status_code": status_code,
                    "status_message": desc,
                    "raw_status": milestone,
                    "flight_info": flight,
                    "pieces": pieces_parsed,
                    "weight": weight_parsed
                })

        return history
