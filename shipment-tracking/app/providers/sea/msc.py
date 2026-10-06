import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

MSC_TRACKING_URL = "https://www.msc.com/api/feature/tools/TrackingInfo"

MSC_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-IN,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://www.msc.com",
    "priority": "u=1, i",
    "referer": "https://www.msc.com/en/track-a-shipment",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
    "Cookie": (
        "AKA_A2=A; "
        "ak_bmsc=627BF281DFDD6EF337A8A117202001DA~000000000000000000000000000000~YAAQvTtAF04zjdWgAQAAs96R9QF/w2bmdPdAo8rT+uOkNgAab936vP+FHqa1nXsmPbHctjwJ9zIDU+hrZ0wXyX7Oolb7izknyPyaegbm1no27I1YppbK3M6aVdLABKem0UI0izrIPiCPDdF5LwZFlVfAYaMpUMj5EzDPFxzxr9sL89qXddrQ57WA2XBKc1jkpdXz8fVadfzXLKOPwNMcK/Jcgy/WStM9/zEESArhI67/F2osFHJZdFnapFK1su+EhGnr+AceupCn+IOG4fpW4SVuZ17f6AoGuIYGMME7hxlidyEOMbLimZKtLa4POt9o9tNVNkWxnlav5DV86qag0KSWucLqwoQidrcB5R1Smb+Zaw09qKdh0eUKL81xVyzfQxi/ur86fXQm; "
        "_clck=1cz7e97%5E2%5Eg9x%5E1%5E2465; msccargo#lang=en; shell#lang=en; "
        "ASP.NET_SessionId=nmidlofcqr5015wwbnvenu0k; SC_ANALYTICS_GLOBAL_COOKIE=8da8a6dfaeac4cc8a151614323ade86b|False; "
        "OptanonAlertBoxClosed=2026-10-01T03:46:34.701Z; _clsk=1p86sq8%5E1790826394705%5E2%5E0%5Ea.clarity.ms%2Fcollect; "
        "_ga=GA1.1.2056677876.1790826386; _gcl_au=1.1.733115898.1790826395; "
        "_ga_2WVVR2C39J=GS2.1.s1790826383$o1$g0$t1790826394$j60$l0$h0$dkcZ3T7tE_-9q5ucnvYDaWhkic4VDWvAtcQ; "
        "_uetsid=b2a13060bd4a11f1a4b2f17547dc1b33; _uetvid=b2a139f0bd4a11f1871f590f3d87dd53; jcoPageCount=1; "
        "OptanonConsent=isGpcEnabled=0&datestamp=Thu+Oct+01+2026+09%3A16%3A34+GMT%2B0530+(India+Standard+Time)&version=202509.1.0&browserGpcFlag=0&isIABGlobal=false&identifierType=&hosts=&consentId=a7daf70c-cfbc-4187-b1f5-b5a40041637a&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A1%2CC0004%3A1%2CC0003%3A1%2CC0001%3A1&iType=1&intType=1; "
        "_yjsu_yjad=1790826395.6d1c6e22-4b76-4539-baa2-01b84b56ef3d; "
        "_ga_7960BT6SN5=GS2.1.s1790826383$o1$g1$t1790826405$j49$l0$h0$dNX1ht028ibw_8O9xhs63lUGOCxuwruj7DA; "
        "_ga_9HMJRMP77C=GS2.1.s1790826383$o1$g1$t1790826405$j49$l0$h0$dDpSpaXg9czni-RjXQnYBFX-nxp1NuTIVDQ; "
        'RT="z=1&dm=www.msc.com&si=b898047d-efcc-4737-8930-3afe9cf0bae4&ss=muozs8i8&sl=1&tt=21b&rl=1&nu=47kw2eps&cl=pd9"; '
        "msccargo#lang=en"
    ),
}

EVENT_CODE_MAP = {
    "DELIVERED": "DLV",
    "CONSIGNEE": "DLV",
    "EMPTY RECEIVED": "MT_RET",
    "DISCHARGED": "DISCH",
    "LOADED": "LOAD",
    "EMPTY TO SHIPPER": "GT_OUT",
    "GATE IN": "GT_IN",
    "GATE OUT": "GT_OUT",
}


def _parse_msc_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    try:
        # Expected format: "DD/MM/YYYY"
        dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return dt.isoformat()
    except Exception:
        return date_str


class MscProvider(BaseProvider):
    name = "msc"
    mode = "SEA"

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        container_id = f"{prefix}{serial}".upper().strip()

        payload = {
            "trackingNumber": container_id,
            "trackingMode": "0",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    MSC_TRACKING_URL,
                    headers=MSC_HEADERS,
                    json=payload,
                )

            latency = round((time.time() - start_time) * 1000, 2)

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"MSC API returned HTTP {resp.status_code}",
                    latency_ms=latency,
                )

            data = resp.json()
            if not data.get("IsSuccess"):
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"MSC shipment not found or query unsuccessful for {container_id}",
                    latency_ms=latency,
                    raw_data=data,
                )

            tracking_data = data.get("Data") or {}
            bol_list = tracking_data.get("BillOfLadings") or []

            if not bol_list:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"No Bill of Lading records found for container {container_id}",
                    latency_ms=latency,
                    raw_data=data,
                )

            primary_bol = bol_list[0]
            gen_info = primary_bol.get("GeneralTrackingInfo") or {}
            origin = gen_info.get("ShippedFrom") or gen_info.get("PortOfLoad")
            destination = gen_info.get("ShippedTo") or gen_info.get("PortOfDischarge")
            overall_delivered = primary_bol.get("Delivered", False)

            containers_info = primary_bol.get("ContainersInfo") or []
            target_container = None
            if containers_info:
                for c in containers_info:
                    if c.get("ContainerNumber", "").upper() == container_id:
                        target_container = c
                        break
                if not target_container:
                    target_container = containers_info[0]

            container_events = (target_container.get("Events") if target_container else []) or []

            # Sort events chronologically (Order 0 is earliest move, higher order is later move)
            sorted_events = sorted(container_events, key=lambda x: x.get("Order", 0))

            parsed_events: List[Dict[str, Any]] = []
            for ev in sorted_events:
                desc = ev.get("Description") or "Status Update"
                location = ev.get("Location") or origin or "SEA PORT"
                un_loc = ev.get("UnLocationCode")
                date_raw = ev.get("Date")
                iso_time = _parse_msc_date(date_raw) or datetime.now(timezone.utc).isoformat()
                details_list = ev.get("Detail") or []

                # Extract vessel / voyage info
                vessel_name = None
                for d in details_list:
                    if d not in ("EMPTY", "LADEN"):
                        vessel_name = d
                        break

                vessel_obj = ev.get("Vessel") or {}
                if vessel_obj.get("IMO") and not vessel_name:
                    vessel_name = f"IMO {vessel_obj.get('IMO')}"

                equipment = ev.get("EquipmentHandling") or {}
                terminal = equipment.get("Name")

                # Build milestone message
                msg_parts = [desc]
                if vessel_name:
                    msg_parts.append(f"Vessel: {vessel_name}")
                if terminal:
                    msg_parts.append(f"Terminal: {terminal}")
                full_msg = " - ".join(msg_parts)

                # Determine standard event code
                desc_upper = desc.upper()
                event_code = "INFO"
                for kw, code in EVENT_CODE_MAP.items():
                    if kw in desc_upper:
                        event_code = code
                        break

                parsed_events.append({
                    "station": f"{location} ({un_loc})" if un_loc else location,
                    "status_code": event_code,
                    "status_message": full_msg,
                    "event_time": iso_time,
                    "flight_info": vessel_name,
                    "pieces": 1,
                    "weight": 24000.0,
                })

            final_status = "In Transit"
            if overall_delivered or (target_container and target_container.get("Delivered")):
                final_status = "Delivered"
            elif parsed_events:
                last_code = parsed_events[-1]["status_code"]
                if last_code in ("DLV", "MT_RET"):
                    final_status = "Delivered"
                elif last_code == "DISCH":
                    final_status = "Discharged"
                elif last_code == "LOAD":
                    final_status = "In Transit"

            return ProviderResult(
                success=True,
                provider_name=self.name,
                status_code=200,
                status=final_status,
                origin=origin,
                destination=destination,
                pieces=1,
                weight={"unit": "kg", "value": 24000.0},
                volume=38.5,
                events=parsed_events,
                latest_event=parsed_events[-1] if parsed_events else None,
                raw_data={
                    "carrier": "Mediterranean Shipping Company (MSC)",
                    "container": container_id,
                    "bill_of_lading": primary_bol.get("BillOfLadingNumber"),
                    "container_type": target_container.get("ContainerType") if target_container else None,
                    "events_count": len(parsed_events),
                },
                latency_ms=latency,
            )

        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to MSC API: {str(exc)}",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error parsing MSC response: {str(exc)}",
                latency_ms=latency,
            )
