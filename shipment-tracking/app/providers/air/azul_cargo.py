import time
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, Any, List

from app.providers.base import BaseProvider, ProviderResult
import logging

logger = logging.getLogger("shipment_tracking.providers.azul_cargo")

class AzulCargoProvider(BaseProvider):
    name = "azul_cargo"
    
    def _map_status_code(self, milestone: str) -> str:
        ms = milestone.lower()
        if "manifest" in ms:
            return "Bkd" # Booked/Manifested
        if "departed" in ms:
            return "Dep"
        if "arrived" in ms:
            return "Arr"
        if "delivered" in ms:
            return "Dlv"
        if "accepted" in ms:
            return "Rcs"
        if "received" in ms:
            return "Rcf"
        return ""
        
    async def track(self, tracking_number: str, prefix: str = "", serial: str = "", **kwargs) -> ProviderResult:
        start_time = time.time()
        url = "https://azulcargoexpress.smartkargo.com/FrmAWBTracking.aspx"
        
        try:
            logger.info(f"Azul Cargo: Tracking {prefix}-{serial}...")
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                viewstate_tag = soup.find('input', {'name': '__VIEWSTATE'})
                vsg_tag = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
                
                if not viewstate_tag or not vsg_tag:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=500,
                        error="Failed to extract ASP.NET viewstate variables.",
                        latency_ms=round((time.time() - start_time) * 1000, 2)
                    )
                
                payload = {
                    "__VIEWSTATE": viewstate_tag['value'],
                    "__VIEWSTATEGENERATOR": vsg_tag['value'],
                    "txtPrefix": prefix,
                    "TextBoxAWBno": serial,
                    "ButtonGO": "Track",
                    "hdnIsAlaska": "false"
                }
                
                post_resp = await client.post(url, data=payload)
                post_resp.raise_for_status()
                post_soup = BeautifulSoup(post_resp.text, 'html.parser')
                
                origin_tag = post_soup.find('span', id='lblOrigin')
                dest_tag = post_soup.find('span', id='lblDestination')
                pcs_tag = post_soup.find('span', id='lblPcs')
                wt_tag = post_soup.find('span', id='lblGrossWt')
                
                if not origin_tag or not dest_tag:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=404,
                        status="NOT_FOUND",
                        error=f"No tracking data found for AWB {prefix}-{serial} on Azul Cargo.",
                        latency_ms=round((time.time() - start_time) * 1000, 2)
                    )
                
                origin = origin_tag.text.strip()
                dest = dest_tag.text.strip()
                pieces_text = pcs_tag.text.strip() if pcs_tag else ""
                wt_text = wt_tag.text.strip() if wt_tag else ""
                
                pieces = None
                if pieces_text:
                    pieces_val = "".join(filter(str.isdigit, pieces_text))
                    if pieces_val:
                        pieces = int(pieces_val)
                        
                weight = None
                if wt_text:
                    wt_val_str = "".join(c for c in wt_text if c.isdigit() or c == '.')
                    if wt_val_str:
                        weight = {"value": float(wt_val_str), "unit": "kg"}
                        
                events = []
                status_table = post_soup.find('table', {'id': 'GridViewAwbTracking'})
                
                if status_table:
                    for row in status_table.find_all('tr')[1:]:
                        cols = row.find_all('td')
                        if len(cols) >= 6:
                            station = cols[0].text.strip()
                            milestone = cols[1].text.strip()
                            flt = cols[4].text.strip()
                            date = cols[5].text.strip()
                            
                            status_code = self._map_status_code(milestone)
                            
                            try:
                                try:
                                    parsed_date = datetime.strptime(date, "%d/%m/%Y %H:%M")
                                except ValueError:
                                    parsed_date = datetime.strptime(date, "%d/%m/%Y")
                                iso_date = parsed_date.isoformat()
                            except ValueError:
                                iso_date = date
                            
                            events.append({
                                "station": station,
                                "status_code": status_code,
                                "status_message": milestone,
                                "event_time": iso_date,
                                "milestone_status": f"{status_code} - {milestone}" if status_code else milestone,
                                "raw_status": milestone
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
                    raw_data={"url": url, "html_length": len(post_resp.text)},
                    latency_ms=round((time.time() - start_time) * 1000, 2)
                )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="Azul Cargo tracking request timed out.",
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
            logger.error(f"Azul Cargo tracking error: {exc}", exc_info=True)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
