import re
import time
import logging
from datetime import datetime
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("shipment_tracking.providers.indigo_cargo")

TRACKING_URL = "https://6ecargo.goindigo.in/FrmAWBTracking.aspx"

BASE_HEADERS = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://6ecargo.goindigo.in",
    "referer": "https://6ecargo.goindigo.in/FrmAWBTracking.aspx",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}


class IndigoCargoProvider(BaseProvider):
    """
    Live provider for IndiGo Cargo (6E Cargo).
    Scrapes the ASP.NET WebForms tracking page at 6ecargo.goindigo.in.
    Flow:
        1. GET the tracking page to obtain __VIEWSTATE and session cookies.
        2. POST with prefix + AWB serial to submit the tracking form.
        3. Parse HTML response with BeautifulSoup to extract milestones.
    """

    name = "indigo_cargo"
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
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                verify=True,
            ) as client:
                # Step 1: GET the tracking page to grab __VIEWSTATE + session cookies
                logger.info(f"IndiGo: Fetching tracking page for session & __VIEWSTATE...")
                get_resp = await client.get(TRACKING_URL, headers={
                    "accept": BASE_HEADERS["accept"],
                    "accept-language": BASE_HEADERS["accept-language"],
                    "user-agent": BASE_HEADERS["user-agent"],
                })
                get_resp.raise_for_status()

                # Extract __VIEWSTATE and other hidden fields from the initial page
                init_soup = BeautifulSoup(get_resp.text, "html.parser")
                viewstate = self._extract_hidden_field(init_soup, "__VIEWSTATE")
                viewstate_generator = self._extract_hidden_field(
                    init_soup, "__VIEWSTATEGENERATOR"
                )

                if not viewstate:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=502,
                        error="Failed to extract __VIEWSTATE from IndiGo tracking page.",
                        latency_ms=round((time.time() - start_time) * 1000, 2),
                    )

                # Step 2: POST the tracking form
                logger.info(
                    f"IndiGo: Submitting tracking form for {prefix}-{serial}..."
                )
                form_data = {
                    "ToolkitScriptManager1_HiddenField": "",
                    "__EVENTTARGET": "",
                    "__EVENTARGUMENT": "",
                    "__VIEWSTATE": viewstate,
                    "__VIEWSTATEGENERATOR": viewstate_generator or "518255C7",
                    "__VIEWSTATEENCRYPTED": "",
                    "txtPrefix": prefix,
                    "TextBoxAWBno": serial,
                    "ButtonGO": "Track",
                    "hdnIsAlaska": "false",
                }

                post_resp = await client.post(
                    TRACKING_URL,
                    data=form_data,
                    headers=BASE_HEADERS,
                )
                post_resp.raise_for_status()
                latency = round((time.time() - start_time) * 1000, 2)

                # Step 3: Parse the HTML response
                return self._parse_tracking_html(
                    html=post_resp.text,
                    prefix=prefix,
                    serial=serial,
                    latency=latency,
                )

        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=408,
                error="IndiGo Cargo tracking request timed out.",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"IndiGo tracking error: {exc}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )

    @staticmethod
    def _extract_hidden_field(soup: BeautifulSoup, field_name: str) -> Optional[str]:
        """Extract value of a hidden input field from the ASP.NET page."""
        tag = soup.find("input", {"name": field_name, "type": "hidden"})
        if tag and tag.get("value"):
            return tag["value"]
        return None

    def _parse_tracking_html(
        self,
        html: str,
        prefix: str,
        serial: str,
        latency: float,
    ) -> ProviderResult:
        """Parse the IndiGo tracking HTML response and extract milestones."""
        soup = BeautifulSoup(html, "html.parser")

        # Check for error messages
        error_label = soup.find("span", {"id": "LabelStatus"})
        if error_label and error_label.get_text(strip=True):
            error_text = error_label.get_text(strip=True)
            logger.warning(f"IndiGo tracking error label: {error_text}")
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=404,
                status="NOT_FOUND",
                error=error_text,
                latency_ms=latency,
            )

        # Extract AWB info
        awb_label = soup.find("span", {"id": "lblAWBNo"})
        if not awb_label:
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=404,
                status="NOT_FOUND",
                error=f"No tracking data found for {prefix}-{serial} on IndiGo Cargo.",
                latency_ms=latency,
            )

        origin = self._get_span_text(soup, "lblOrigin")
        destination = self._get_span_text(soup, "lblDestination")
        latest_activity = self._get_span_text(soup, "lblLatestActivity")

        # Parse pieces and weight from lblPcs and lblGrossWt
        pieces = self._parse_pieces(self._get_span_text(soup, "lblPcs"))
        weight_str = self._get_span_text(soup, "lblGrossWt")
        weight_val = self._parse_weight(weight_str)

        # Determine overall status from latest activity
        status = self._determine_status(latest_activity)

        # Extract events from the Status History table (GridViewAwbTracking)
        events = self._parse_status_history_table(soup)

        # Build latest event from the last event in the list
        latest_event = None
        if events:
            latest_event = events[-1]

        return ProviderResult(
            success=True,
            provider_name=self.name,
            status_code=200,
            status=status,
            origin=origin,
            destination=destination,
            pieces=pieces,
            weight={"value": weight_val, "unit": "kg"} if weight_val else None,
            volume=None,
            events=events,
            latest_event=latest_event,
            raw_data={
                "carrier": "IndiGo Cargo",
                "awb": f"{prefix}-{serial}",
                "latest_activity": latest_activity,
            },
            latency_ms=latency,
        )

    def _parse_status_history_table(self, soup: BeautifulSoup) -> list:
        """
        Parse the 'Status History' GridViewAwbTracking table.
        Columns: Station | Milestone | Pcs | Weight | Flight# | Flight Date | Org | Dest | ULD | Event Date-Time
        """
        events = []
        table = soup.find("table", {"id": "GridViewAwbTracking"})
        if not table:
            logger.warning("IndiGo: GridViewAwbTracking table not found in HTML.")
            return events

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 10:
                continue  # Skip header row or malformed rows

            station = cells[0].get_text(strip=True)
            milestone = cells[1].get_text(strip=True)
            pcs_text = cells[2].get_text(strip=True)
            weight_text = cells[3].get_text(strip=True)
            flight_no = cells[4].get_text(strip=True)
            flight_date = cells[5].get_text(strip=True)
            org = cells[6].get_text(strip=True)
            dest = cells[7].get_text(strip=True)
            uld = cells[8].get_text(strip=True)
            event_datetime_str = cells[9].get_text(strip=True)

            # Parse event datetime
            event_time = self._parse_indigo_datetime(event_datetime_str)

            # Map milestone to FSU-style status code
            status_code = self._milestone_to_status_code(milestone)

            # Parse pieces as integer
            pcs_val = None
            if pcs_text and pcs_text.isdigit():
                pcs_val = int(pcs_text)

            # Parse weight value
            wt_val = self._parse_weight(weight_text)

            # Build flight info string
            flight_info = flight_no
            if flight_date:
                flight_info = f"{flight_no} / {flight_date}"

            events.append({
                "station": station,
                "status_code": status_code,
                "status_message": milestone,
                "event_time": event_time,
                "flight_info": flight_info,
                "pieces": pcs_val,
                "weight": wt_val,
                "raw_status": milestone,
            })

        return events

    @staticmethod
    def _get_span_text(soup: BeautifulSoup, span_id: str) -> Optional[str]:
        """Safely extract text from a <span> by its id."""
        tag = soup.find("span", {"id": span_id})
        return tag.get_text(strip=True) if tag else None

    @staticmethod
    def _parse_pieces(pcs_text: Optional[str]) -> Optional[int]:
        """Parse '1 P' or '13 P' into integer."""
        if not pcs_text:
            return None
        match = re.match(r"(\d+)", pcs_text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_weight(weight_text: Optional[str]) -> Optional[float]:
        """Parse '231.00 Kgs' or '101.00 Kgs' into float."""
        if not weight_text:
            return None
        match = re.match(r"([\d.]+)", weight_text)
        return float(match.group(1)) if match else None

    @staticmethod
    def _parse_indigo_datetime(dt_str: Optional[str]) -> Optional[str]:
        """
        Parse IndiGo datetime format 'DD/MM/YYYY HH:MM:SS' or 'DD/MM/YYYY HH:MM'
        into ISO 8601 string.
        """
        if not dt_str:
            return None
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                return dt.isoformat()
            except ValueError:
                continue
        return dt_str  # Return raw string if parsing fails

    @staticmethod
    def _milestone_to_status_code(milestone: str) -> str:
        """Map IndiGo milestone text to standard FSU status codes."""
        milestone_upper = milestone.upper().strip()
        mapping = {
            "BOOKED": "BKD",
            "ACCEPTED": "RCS",
            "MANIFESTED": "MAN",
            "DEPARTED": "DEP",
            "ARRIVED": "ARR",
            "DELIVERED": "DLV",
            "DELIVERED SAVED": "DLV",
            "RECEIVED FROM FLIGHT": "RCF",
            "NOTIFIED": "NFD",
            "CHECKED IN": "RCS",
            "TRANSFERRED": "TFD",
        }
        return mapping.get(milestone_upper, milestone_upper)

    @staticmethod
    def _determine_status(latest_activity: Optional[str]) -> str:
        """Determine overall shipment status from the latest activity text."""
        if not latest_activity:
            return "Unknown"
        activity_upper = latest_activity.upper()
        if "DELIVERED" in activity_upper:
            return "Delivered"
        elif "ARRIVED" in activity_upper:
            return "Arrived"
        elif "DEPARTED" in activity_upper:
            return "In Transit"
        elif "ACCEPTED" in activity_upper or "BOOKED" in activity_upper:
            return "Booked"
        elif "MANIFESTED" in activity_upper:
            return "Manifested"
        return "In Transit"
