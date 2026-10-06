import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup
from app.providers.base import BaseProvider, ProviderResult

JAL_TRACK_URL = "https://www.cargoweb2.jal.co.jp/JalCargoWeb/sp/en/intlTracingResult.do"

JAL_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.jal.co.jp",
    "Referer": "https://www.jal.co.jp/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

MONTH_MAP = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

STATUS_CODE_MAP = {
    "RESERVED": "BKD",
    "BOOKED": "BKD",
    "ACCEPTING": "RCS",
    "ACCEPTED": "RCS",
    "DEPARTED": "DEP",
    "ARRIVED": "ARR",
    "SHIPMENT AVAILABILITY": "NFD",
    "AVAILABLE": "NFD",
    "DELIVERED": "DLV",
}


def _parse_jal_datetime(date_str: Optional[str], time_str: Optional[str]) -> Optional[str]:
    if not date_str or date_str == "-" or not time_str or time_str == "-":
        return None
    m = re.match(r"(\d{1,2})([A-Za-z]{3})", date_str.strip().upper())
    if not m:
        return f"{date_str} {time_str}".strip()
    day, mon = m.groups()
    mon_num = MONTH_MAP.get(mon, "01")
    year = datetime.now(timezone.utc).year
    t = time_str.strip()
    if len(t) == 5 and ":" in t:
        return f"{year}-{mon_num}-{day.zfill(2)}T{t}:00"
    return f"{year}-{mon_num}-{day.zfill(2)}T{t}"


class JalCargoProvider(BaseProvider):
    name = "jal_cargo"
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

        # Support both standard prefix 131 and alias 1331
        effective_prefix = "131" if prefix in ("131", "1331") else prefix
        if effective_prefix != "131":
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=400,
                error=f"Prefix '{prefix}' not handled by JAL Cargo (expects 131)",
                latency_ms=latency,
            )

        payload = {
            "searchType": "00",
            "awbNoPrefix1": effective_prefix,
            "awbNoSuffix1": serial,
            "houseNo": "",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.post(
                    JAL_TRACK_URL,
                    headers=JAL_HEADERS,
                    data=payload,
                )

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"JAL Cargo Web returned HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            soup = BeautifulSoup(resp.text, "html.parser")

            # Check for error container
            err_box = soup.find("div", class_="errorArea") or soup.find("p", class_="error")
            if err_box and err_box.get_text(strip=True):
                err_text = err_box.get_text(" ", strip=True)
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"JAL Cargo tracking error: {err_text}",
                    latency_ms=latency,
                )

            # 1. Parse common header details (origin, destination, pieces, weight)
            details_div = soup.find("div", class_="details")
            origin = None
            destination = None
            pieces = None
            weight_val = None
            weight_unit = "kg"

            if details_div:
                for box in details_div.find_all("div"):
                    h3 = box.find("h3")
                    p = box.find("p")
                    if h3 and p:
                        title = h3.get_text(strip=True).lower()
                        val = p.get_text(" ", strip=True)
                        if "origin" in title:
                            origin = val
                        elif "destination" in title:
                            destination = val
                        elif "pieces" in title:
                            try:
                                pieces = int(re.sub(r"\D", "", val))
                            except Exception:
                                pass
                        elif "weight" in title:
                            # e.g., "281.0 KGS"
                            parts = val.split()
                            if parts:
                                try:
                                    weight_val = float(parts[0])
                                except Exception:
                                    pass
                                if len(parts) > 1 and "kg" in parts[1].lower():
                                    weight_unit = "kg"

            # 2. Parse routing unit (Milestone events)
            routing_div = soup.find("div", class_="routingUnit")
            if not routing_div and not origin and not destination:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"No shipment records found for JAL AWB {effective_prefix}-{serial}",
                    latency_ms=latency,
                )

            events: List[Dict[str, Any]] = []
            active_status_text: Optional[str] = None

            if routing_div:
                current_h3 = None
                current_dls = []
                for elem in routing_div.children:
                    if getattr(elem, "name", None) == "h3":
                        if current_h3:
                            events.append((current_h3, current_dls))
                        current_h3 = elem
                        current_dls = []
                    elif getattr(elem, "name", None) == "dl" and current_h3 is not None:
                        current_dls.append(elem)
                if current_h3:
                    events.append((current_h3, current_dls))

            parsed_events: List[Dict[str, Any]] = []

            for h3_elem, dl_elems in events:
                classes = h3_elem.get("class", [])
                span = h3_elem.find("span")
                headline = span.get_text(" ", strip=True) if span else h3_elem.get_text(" ", strip=True)

                if "setRed" in classes:
                    active_status_text = headline

                info_map: Dict[str, str] = {}
                for dl in dl_elems:
                    dt = dl.find("dt")
                    dd = dl.find("dd")
                    if dt and dd:
                        k = dt.get_text(strip=True).replace("：", "").replace("*", "").strip()
                        v = dd.get_text(" ", strip=True)
                        info_map[k] = v

                # Determine milestone status code
                first_word = headline.split()[0].upper() if headline else "INFO"
                status_code = STATUS_CODE_MAP.get(first_word, "INFO")

                station = info_map.get("Airport") or (origin if status_code in ["BKD", "RCS"] else destination)
                flight = info_map.get("Flight")
                uld = info_map.get("ULD Number")
                event_iso = _parse_jal_datetime(info_map.get("Date"), info_map.get("Time"))

                flight_info_str = flight
                if uld:
                    flight_info_str = f"{flight} (ULD: {uld})" if flight else f"ULD: {uld}"

                parsed_events.append({
                    "station": station,
                    "status_code": status_code,
                    "status_message": headline,
                    "event_time": event_iso or datetime.now(timezone.utc).isoformat(),
                    "flight_info": flight_info_str,
                    "pieces": pieces,
                    "weight": weight_val,
                })

            # Derive current status
            final_status = "In Transit"
            status_source = active_status_text or (parsed_events[-1]["status_message"] if parsed_events else "")
            status_source_upper = status_source.upper()

            if "DELIVERED" in status_source_upper:
                final_status = "Delivered"
            elif "AVAILABILITY" in status_source_upper or "AVAILABLE" in status_source_upper:
                final_status = "Available for Pickup"
            elif "ARRIVED" in status_source_upper:
                final_status = "Arrived"
            elif "DEPARTED" in status_source_upper:
                final_status = "In Transit"
            elif "ACCEPTED" in status_source_upper or "ACCEPTING" in status_source_upper:
                final_status = "Accepted"
            elif "RESERVED" in status_source_upper:
                final_status = "Booked"

            weight_dict = {"unit": weight_unit, "value": weight_val} if weight_val is not None else None

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=final_status,
                origin=origin,
                destination=destination,
                pieces=pieces,
                weight=weight_dict,
                events=parsed_events,
                latest_event=parsed_events[-1] if parsed_events else None,
                raw_data={
                    "carrier": "Japan Airlines Cargo (JAL)",
                    "awb": f"{effective_prefix}-{serial}",
                    "milestones_count": len(parsed_events),
                },
                latency_ms=latency,
            )

        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to JAL Cargo: {str(exc)}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error parsing JAL Cargo HTML: {str(exc)}",
                latency_ms=latency,
            )
