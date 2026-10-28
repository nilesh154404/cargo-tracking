import re
import threading
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from app.db.models import LocationCoordinate
import app.db.session as db_session

class LocationMatcher:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._initialized = False
        self._airport_by_iata: Dict[str, Dict[str, Any]] = {}
        self._airport_by_icao: Dict[str, Dict[str, Any]] = {}
        self._seaport_by_code: Dict[str, Dict[str, Any]] = {}
        self._locations_by_name: Dict[str, List[Dict[str, Any]]] = {}
        self._locations_by_city: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    def get_instance(cls) -> "LocationMatcher":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_loaded(self):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self._load_from_db()
            self._initialized = True

    def _load_from_db(self):
        if db_session.SessionLocal is None:
            db_session.init_db_engine()
        db = db_session.SessionLocal()
        try:
            records = db.execute(select(LocationCoordinate)).scalars().all()
            for r in records:
                loc_dict = {
                    "id": r.id,
                    "location_type": r.location_type,
                    "code": r.code,
                    "display_code": r.display_code,
                    "icao_code": r.icao_code,
                    "name": r.name,
                    "city": r.city,
                    "country": r.country,
                    "lat": r.latitude,
                    "lng": r.longitude,
                }

                if r.location_type == "AIRPORT":
                    if r.code:
                        self._airport_by_iata[r.code.upper()] = loc_dict
                    if r.icao_code:
                        self._airport_by_icao[r.icao_code.upper()] = loc_dict
                elif r.location_type == "SEAPORT":
                    if r.code:
                        norm = r.code.replace(" ", "").upper()
                        self._seaport_by_code[norm] = loc_dict
                    if r.display_code:
                        self._seaport_by_code[r.display_code.upper()] = loc_dict

                # Index by normalized name and city for fast fuzzy/substring lookups
                if r.name:
                    n_key = self._normalize_str(r.name)
                    if n_key:
                        self._locations_by_name.setdefault(n_key, []).append(loc_dict)
                if r.city:
                    c_key = self._normalize_str(r.city)
                    if c_key:
                        self._locations_by_city.setdefault(c_key, []).append(loc_dict)
        finally:
            db.close()

    @staticmethod
    def _normalize_str(s: str) -> str:
        if not s:
            return ""
        # Remove parentheses content and non-alphanumeric characters
        s_clean = re.sub(r"\(.*?\)", "", s)
        s_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", s_clean).strip().lower()
        return re.sub(r"\s+", " ", s_clean)

    def match_location(self, station_text: Optional[str], mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Match station, origin, or destination string against airport and seaport coordinates.
        Supports:
          1. Parenthesized UN/LOCODE, e.g., 'VISAKHAPATNAM, IN (INVTZ)' -> INVTZ
          2. Exact 3-letter IATA code, e.g., 'HKG', 'BOM', 'SIN', 'CTU'
          3. Exact 5-letter UN/LOCODE, e.g., 'BEANR', 'RULED', 'INMUN'
          4. Exact 4-letter ICAO code, e.g., 'VHHH', 'OAKN'
          5. City / Port name extracted from comma or delimiter, e.g., 'MUNDRA, IN', 'HAMAD, QA'
          6. Substring name matching in facility names, e.g., 'Adani Mundra Container Terminal 2'
        """
        if not station_text or not isinstance(station_text, str):
            return None

        clean_text = station_text.strip()
        if not clean_text or clean_text.upper() in ("UNKNOWN", "N/A", "NONE", "PORT / TERMINAL"):
            return None

        self._ensure_loaded()
        mode_upper = mode.upper() if mode else None

        # Tier 1: Look for UN/LOCODE in parentheses: e.g. "VISAKHAPATNAM, IN (INVTZ)" or "(BEANR)"
        paren_match = re.search(r"\(([A-Za-z0-9\s]{3,6})\)", clean_text)
        if paren_match:
            candidate = paren_match.group(1).replace(" ", "").upper()
            # Check seaport
            if candidate in self._seaport_by_code:
                return self._format_result(self._seaport_by_code[candidate])
            # Check airport IATA
            if candidate in self._airport_by_iata:
                return self._format_result(self._airport_by_iata[candidate])
            # Check airport ICAO
            if candidate in self._airport_by_icao:
                return self._format_result(self._airport_by_icao[candidate])

        # Tier 2: Check if entire string is exact code (e.g. "HKG", "BOM", "CTU", "BEANR", "INMUN")
        raw_token = clean_text.replace(" ", "").upper()
        if len(raw_token) == 3:
            if mode_upper != "SEA" and raw_token in self._airport_by_iata:
                return self._format_result(self._airport_by_iata[raw_token])
        elif len(raw_token) == 4:
            if mode_upper != "SEA" and raw_token in self._airport_by_icao:
                return self._format_result(self._airport_by_icao[raw_token])
        elif len(raw_token) == 5:
            if mode_upper != "AIR" and raw_token in self._seaport_by_code:
                return self._format_result(self._seaport_by_code[raw_token])

        # Tier 3: Parse standard "CITY, COUNTRY_CODE" format e.g. "MUNDRA, IN", "HAMAD, QA", "SAINT PETERSBURG, RU"
        parts = [p.strip() for p in clean_text.split(",") if p.strip()]
        if len(parts) >= 2:
            city_part = parts[0]
            norm_city = self._normalize_str(city_part)
            # Try city exact match
            res = self._match_by_name_or_city(norm_city, mode_upper)
            if res:
                return res

        # Tier 4: Look for embedded 3-letter IATA code if mode is AIR
        if mode_upper == "AIR" or not mode_upper:
            iata_candidates = re.findall(r"\b([A-Z]{3})\b", clean_text)
            for cand in iata_candidates:
                if cand in self._airport_by_iata:
                    return self._format_result(self._airport_by_iata[cand])

        # Tier 5: Look for embedded 5-letter UN/LOCODE if mode is SEA
        if mode_upper == "SEA" or not mode_upper:
            locode_candidates = re.findall(r"\b([A-Z]{5})\b", clean_text)
            for cand in locode_candidates:
                if cand in self._seaport_by_code:
                    return self._format_result(self._seaport_by_code[cand])

        # Tier 6: Substring / keyword search in text against known port and city names
        norm_full = self._normalize_str(clean_text)
        res = self._search_name_in_text(norm_full, mode_upper)
        if res:
            return res

        return None

    def _match_by_name_or_city(self, norm_query: str, mode: Optional[str]) -> Optional[Dict[str, Any]]:
        candidates = []
        if norm_query in self._locations_by_city:
            candidates.extend(self._locations_by_city[norm_query])
        if norm_query in self._locations_by_name:
            candidates.extend(self._locations_by_name[norm_query])

        if not candidates:
            return None

        # Filter by mode preference if provided
        if mode:
            mode_matches = [c for c in candidates if c["location_type"] == mode]
            if mode_matches:
                return self._format_result(mode_matches[0])

        return self._format_result(candidates[0])

    def _search_name_in_text(self, norm_text: str, mode: Optional[str]) -> Optional[Dict[str, Any]]:
        tokens = set(norm_text.split())
        # First check specific important keywords with length >= 4
        matched_candidates = []

        # Check port names
        for norm_name, loc_list in self._locations_by_name.items():
            if len(norm_name) >= 4 and norm_name in norm_text:
                matched_candidates.extend(loc_list)

        # Check cities
        for norm_city, loc_list in self._locations_by_city.items():
            if len(norm_city) >= 4 and norm_city in norm_text:
                matched_candidates.extend(loc_list)

        if not matched_candidates:
            return None

        # Deduplicate candidates while preserving priority
        unique = []
        seen = set()
        for c in matched_candidates:
            key = (c["location_type"], c["code"])
            if key not in seen:
                seen.add(key)
                unique.append(c)

        if mode:
            preferred = [c for c in unique if c["location_type"] == mode]
            if preferred:
                return self._format_result(preferred[0])

        return self._format_result(unique[0])

    def _format_result(self, loc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "lat": float(loc["lat"]),
            "lng": float(loc["lng"]),
            "matched_code": loc.get("code") or loc.get("display_code") or loc.get("icao_code"),
            "matched_name": loc.get("name"),
            "location_type": loc.get("location_type"),
            "city": loc.get("city"),
            "country": loc.get("country"),
        }


# Global singleton instance
location_matcher = LocationMatcher.get_instance()


def match_location(station_text: Optional[str], mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return location_matcher.match_location(station_text, mode)
