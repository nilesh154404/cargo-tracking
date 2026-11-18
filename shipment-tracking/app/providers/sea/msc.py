import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult
from app.services.location_matcher import match_location

MSC_TRACKING_URL = "https://www.msc.com/api/feature/tools/TrackingInfo"

MSC_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://www.msc.com",
    "priority": "u=1, i",
    "referer": "https://www.msc.com/en/track-a-shipment",
    "sec-ch-ua": '"Not-A.Brand";v="99", "Google Chrome";v="157", "Chromium";v="157"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
    "Cookie": (
        "currentLocation=IN; currentAgency=169; SC_ANALYTICS_GLOBAL_COOKIE=0cfb4870533d41be9a5bc38e30afc23d|True; "
        "OptanonAlertBoxClosed=2026-10-23T15:24:22.498Z; _ga=GA1.1.939757805.1792769062; _gcl_au=1.1.631815865.1792769063; "
        "_yjsu_yjad=1792769062.07574e5d-f49b-4d45-add4-730798e5b205; AKA_A2=A; "
        "ak_bmsc=278EEB0BACAF05B075A0ACB0789CF3B3~000000000000000000000000000000~YAAQvTtAFyD+ntKhAQAAVfbn7AElkt9jPlL8pDISRJ4zNTciJoQt2GrErToehhiqIKGrDrUQwX/jTt/Rfwd0tEcV5b9Vp6aVcgYNcB840h5uNSxZz07dkPZlLsRZoLxbclJaQ2lV+1zoPSbA83mUQx03RjUZIfP6DzcbKxHXA8Pekyg+7bUHJbk4CmJfq85jQKqy7ojkk2JzbXXVYS0LIxvEHAAnLz3E6Qhd2Sj6YdRJz54l3jdhXD4nCeS2xVge70eNozmW8Bqj8BVC/enI05Nr9wBgxx0N2arl9g36LKtK1E29rEkJPqbbr59wzH6ObtyhHt6Bh/HDT+ytSTJ4gBI2L2mEQ/mV7o9HR+TRUFYUlFQo9Nzs9cmpIc2u+idVSQwx5/WpWImp; "
        "OptanonConsent=isGpcEnabled=0&datestamp=Wed+Nov+18+2026+09%3A56%3A27+GMT%2B0530+(India+Standard+Time)&version=202509.1.0&browserGpcFlag=0&isIABGlobal=false&identifierType=&hosts=&consentId=5030b9ca-4188-4ce9-835e-ac88282fadac&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A1%2CC0004%3A1%2CC0003%3A1%2CC0001%3A1&iType=1&intType=1&geolocation=IN%3BMH&AwaitingReconsent=false; "
        "jcoPageCount=1; _clck=105auhx%5E2%5Egb9%5E1%5E2487; _uetsid=396b0150e30811f1b036a34259c1a665; _uetvid=d2de1a90cef511f1ae2287f532c261d0; "
        "_clsk=xt7jib%5E1794975990512%5E1%5E0%5Ea.clarity.ms%2Fcollect; msccargo#lang=en; shell#lang=en; "
        "ASP.NET_SessionId=ggidp1vybqiyyno4uqbbqpgx; "
        "_ga_9HMJRMP77C=GS2.1.s1794975988$o14$g1$t1794976134$j53$l0$h0$dVdgQzlpRmHkpB2LquNrv4IV3MJMeB21GBg; "
        "_ga_7960BT6SN5=GS2.1.s1794975988$o14$g1$t1794976142$j45$l0$h0$dTgq7A185ziU97EutWQrUDQfxyhq5-kU6Vw; "
        'RT="z=1&dm=www.msc.com&si=53a81045-3c46-48c6-84d2-540a5b48305f&ss=mwlmcv8y&sl=1&tt=10l&rl=1&ld=12x&nu=47kw2eps&cl=443c"; '
        "_ga_2WVVR2C39J=GS2.1.s1794976134$o9$g0$t1794976178$j16$l0$h0$dnZIT8bfPE8_bGbK32isAuENwHzxl3yhoFg"
    ),
}

MSC_MILESTONE_MAP = [
    ("EMPTY TO SHIPPER", ("E012", "Empty Equipment Dispatched")),
    ("EXPORT RECEIVED AT CY", ("E040", "Gate In to Outbound Terminal")),
    ("GATE IN", ("E040", "Gate In to Outbound Terminal")),
    ("EXPORT LOADED ON VESSEL", ("E058", "Loaded on Export Vessel")),
    ("LOADED ON VESSEL", ("E058", "Loaded on Export Vessel")),
    ("VESSEL DEPARTURE", ("E061", "Vessel Departure")),
    ("DEPARTED", ("E061", "Vessel Departure")),
    ("FULL TRANSSHIPMENT DISCHARGED", ("E089", "Full Transshipment Discharged")),
    ("TRANSSHIPMENT DISCHARGED", ("E089", "Discharged from Transshipment Vessel")),
    ("FULL INTENDED TRANSSHIPMENT", ("E090", "Full Intended Transshipment")),
    ("INTENDED TRANSSHIPMENT", ("E090", "Intended Transshipment")),
    ("TRANSSHIPMENT LOADED", ("E090", "Transshipment Loaded")),
    ("ESTIMATED TIME OF ARRIVAL", ("E080", "Estimated Time of Arrival")),
    ("VESSEL ARRIVAL", ("E080", "Vessel Arrival")),
    ("IMPORT DISCHARGED", ("E089", "Discharged from Import Vessel")),
    ("DISCHARGED", ("E089", "Discharged from Vessel")),
    ("GATE OUT", ("E106", "Gate Out from Inbound Terminal for Delivery to Consignee")),
    ("IMPORT DELIVERED", ("E106", "Gate Out from Inbound Terminal for Delivery to Consignee")),
    ("EMPTY RECEIVED", ("E138", "Empty Container Returned from Customer")),
    ("EMPTY RETURNED", ("E138", "Empty Container Returned from Customer")),
]


def _parse_msc_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        try:
            dt = datetime.strptime(date_str.strip(), "%d/%m/%Y %H:%M")
            return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        **kwargs: Any,
    ) -> ProviderResult:
        start_time = time.time()

        cntr_input = (
            kwargs.get("container_no")
            or kwargs.get("cntr_no")
            or ""
        ).strip().upper()

        bkg_input = (
            kwargs.get("mawb_obl_no")
            or kwargs.get("booking_no")
            or kwargs.get("billing_no")
            or kwargs.get("bl_no")
            or ""
        ).strip().upper()

        target_container = cntr_input or tracking_number.strip().upper()

        if bkg_input:
            query_tracking_no = bkg_input
        else:
            query_tracking_no = target_container or f"{prefix}{serial}".upper().strip()

        payload = {
            "trackingNumber": query_tracking_no,
            "trackingMode": "0",
        }

        curl_cmd = self.build_curl_command("POST", MSC_TRACKING_URL, headers=MSC_HEADERS, body=payload)
        response_text = None

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    MSC_TRACKING_URL,
                    headers=MSC_HEADERS,
                    json=payload,
                )

            latency = round((time.time() - start_time) * 1000, 2)
            response_text = resp.text

            if resp.status_code != 200:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=resp.status_code,
                    error=f"MSC API returned HTTP {resp.status_code}",
                    request_curl=curl_cmd,
                    response_body=response_text,
                    latency_ms=latency,
                )

            data = resp.json()
            if not data.get("IsSuccess"):
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"MSC shipment not found or query unsuccessful for {query_tracking_no}",
                    request_curl=curl_cmd,
                    response_body=response_text,
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
                    error=f"No Bill of Lading records found for MSC shipment {query_tracking_no}",
                    request_curl=curl_cmd,
                    response_body=response_text,
                    latency_ms=latency,
                    raw_data=data,
                )

            primary_bol = bol_list[0]
            gen_info = primary_bol.get("GeneralTrackingInfo") or {}
            origin = gen_info.get("ShippedFrom") or gen_info.get("PortOfLoad")
            destination = gen_info.get("ShippedTo") or gen_info.get("PortOfDischarge")
            overall_delivered = primary_bol.get("Delivered", False)
            bol_number = primary_bol.get("BillOfLadingNumber") or query_tracking_no

            containers_info = primary_bol.get("ContainersInfo") or []
            selected_container = None

            if containers_info:
                if target_container:
                    for c in containers_info:
                        c_num = (c.get("ContainerNumber") or "").strip().upper()
                        if c_num == target_container:
                            selected_container = c
                            break

                if not selected_container:
                    selected_container = containers_info[0]

            if not selected_container:
                return ProviderResult(
                    success=False,
                    provider_name=self.name,
                    status_code=404,
                    error=f"Container {target_container} not found under MSC Bill of Lading {bol_number}",
                    request_curl=curl_cmd,
                    response_body=response_text,
                    latency_ms=latency,
                    raw_data=data,
                )

            final_container_no = (selected_container.get("ContainerNumber") or target_container).strip().upper()
            container_events = selected_container.get("Events") or []

            chronological_events = sorted(container_events, key=lambda x: x.get("Order", 0))

            raw_events: List[Dict[str, Any]] = []
            for ev in chronological_events:
                desc = (ev.get("Description") or "Status Update").strip()
                order = ev.get("Order", 0)
                date_raw = ev.get("Date")
                iso_time = _parse_msc_date(date_raw) or datetime.now(timezone.utc).isoformat()
                location = ev.get("Location") or origin or "SEA PORT"
                un_loc = ev.get("UnLocationCode")
                details_list = ev.get("Detail") or []

                desc_upper = desc.upper()
                is_estimated = False
                if "ESTIMATED" in desc_upper or "INTENDED" in desc_upper or "EXPECTED" in desc_upper:
                    is_estimated = True
                else:
                    try:
                        ev_date = datetime.strptime(str(date_raw).strip(), "%d/%m/%Y").date()
                        if ev_date > datetime.now(timezone.utc).date():
                            is_estimated = True
                    except Exception:
                        pass

                raw_status = "ESTIMATED" if is_estimated else "ACTUAL"

                status_code = "INFO"
                status_msg = desc
                for kw, (code, canonical_msg) in MSC_MILESTONE_MAP:
                    if kw in desc_upper:
                        status_code = code
                        status_msg = canonical_msg
                        break

                non_state_details = [d for d in details_list if str(d).upper() not in ("EMPTY", "LADEN")]
                vessel_name = None
                voyage_no = None
                if len(non_state_details) >= 2:
                    vessel_name = str(non_state_details[0])
                    voyage_no = str(non_state_details[1])
                elif len(non_state_details) == 1:
                    vessel_name = str(non_state_details[0])

                vessel_obj = ev.get("Vessel") or {}
                if not vessel_name and vessel_obj.get("IMO"):
                    vessel_name = f"IMO {vessel_obj.get('IMO')}"

                if vessel_name and voyage_no:
                    flight_info = f"{final_container_no} | {vessel_name} (Voyage {voyage_no})"
                elif vessel_name:
                    flight_info = f"{final_container_no} | {vessel_name}"
                else:
                    flight_info = final_container_no

                equipment = ev.get("EquipmentHandling") or {}
                terminal = equipment.get("Name")
                if terminal:
                    station_str = f"{location} ({terminal})"
                elif un_loc:
                    station_str = f"{location} ({un_loc})"
                else:
                    station_str = location

                coords = (
                    match_location(un_loc, "SEA")
                    or match_location(location, "SEA")
                    or match_location(station_str, "SEA")
                )

                raw_events.append({
                    "station": station_str,
                    "status_code": status_code,
                    "status_message": status_msg,
                    "event_time": iso_time,
                    "flight_info": flight_info,
                    "pieces": 1,
                    "weight": 24000.0,
                    "raw_status": raw_status,
                    "coordinates": coords,
                    "_order": order,
                })

            actual_events = [e for e in raw_events if e["raw_status"] == "ACTUAL"]
            active_target = actual_events[-1] if actual_events else (raw_events[-1] if raw_events else None)

            for e in raw_events:
                is_act = (e is active_target)
                e["active"] = is_act
                e["is_active"] = is_act

            raw_events.sort(key=lambda x: (x.get("event_time") or "", x.get("_order", 0)), reverse=True)
            for e in raw_events:
                e.pop("_order", None)

            final_status = "In Transit"
            if overall_delivered or (selected_container and selected_container.get("Delivered")):
                final_status = "Delivered"
            elif active_target:
                code = active_target.get("status_code")
                if code in ("E106", "E138", "DLV"):
                    final_status = "Delivered"
                elif code in ("E089", "DISCH"):
                    final_status = "Discharged"
                elif code in ("E040", "GT_IN"):
                    final_status = "Gate In to Outbound Terminal"
                elif code in ("E058", "E061", "E090", "LOAD"):
                    final_status = "In Transit"

            latest_event_item = active_target if active_target else (raw_events[0] if raw_events else None)

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
                events=raw_events,
                latest_event=latest_event_item,
                raw_data={
                    "carrier": "Mediterranean Shipping Company (MSC)",
                    "container": final_container_no,
                    "bill_of_lading": bol_number,
                    "container_type": selected_container.get("ContainerType"),
                    "events_count": len(raw_events),
                },
                request_curl=curl_cmd,
                response_body=response_text,
                latency_ms=latency,
            )

        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to MSC API: {str(exc)}",
                request_curl=curl_cmd,
                response_body=response_text,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error parsing MSC response: {str(exc)}",
                request_curl=curl_cmd,
                response_body=response_text,
                latency_ms=latency,
            )

        except httpx.RequestError as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Network exception connecting to MSC API: {str(exc)}",
                request_curl=curl_cmd,
                response_body=response_text,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=f"Error parsing MSC response: {str(exc)}",
                request_curl=curl_cmd,
                response_body=response_text,
                latency_ms=latency,
            )
