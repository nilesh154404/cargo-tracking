import pytest
from app.services.location_matcher import match_location, LocationMatcher
from app.schemas.tracking import (
    UnifiedTrackingResponse,
    UnifiedTrackingEvent,
    LocationCoordinates,
    CarrierInfo,
    AgentDecisionTrail,
    to_mobile_app_response,
)
from app.tools.db_tools import DatabasePersistenceTool
import app.db.session as db_session
from app.db.models import LocationCoordinate, Shipment, TrackingEvent


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db_session.init_db_engine()


class TestLocationMatcher:

    def test_air_iata_matching(self):
        # Hong Kong
        hkg = match_location("HKG", "AIR")
        assert hkg is not None
        assert hkg["matched_code"] == "HKG"
        assert hkg["location_type"] == "AIRPORT"
        assert abs(hkg["lat"] - 22.31184) < 0.05
        assert abs(hkg["lng"] - 113.91486) < 0.05

        # Mumbai
        bom = match_location("BOM", "AIR")
        assert bom is not None
        assert bom["matched_code"] == "BOM"
        assert abs(bom["lat"] - 19.08869) < 0.05
        assert abs(bom["lng"] - 72.86789) < 0.05

        # Bengaluru
        blr = match_location("BLR", "AIR")
        assert blr is not None
        assert blr["matched_code"] == "BLR"

        # Singapore
        sin = match_location("SIN", "AIR")
        assert sin is not None
        assert sin["matched_code"] == "SIN"

    def test_sea_unlocode_parentheses_matching(self):
        # Visakhapatnam
        vtz = match_location("VISAKHAPATNAM, IN (INVTZ)", "SEA")
        assert vtz is not None
        assert vtz["matched_code"] == "INVTZ"
        assert vtz["location_type"] == "SEAPORT"
        assert abs(vtz["lat"] - 17.7) < 0.1
        assert abs(vtz["lng"] - 83.3) < 0.1

        # Antwerp
        anr = match_location("ANTWERP, BE (BEANR)", "SEA")
        assert anr is not None
        assert anr["matched_code"] == "BEANR"
        assert abs(anr["lat"] - 51.21667) < 0.1

        # Colombo
        cmb = match_location("COLOMBO, LK (LKCMB)", "SEA")
        assert cmb is not None
        assert cmb["matched_code"] == "LKCMB"

        # Saint Petersburg
        led = match_location("SAINT PETERSBURG, RU (RULED)", "SEA")
        assert led is not None
        assert led["matched_code"] == "RULED"

    def test_sea_port_city_and_facility_matching(self):
        # Mundra Port
        mun = match_location("MUNDRA, IN", "SEA")
        assert mun is not None
        assert mun["matched_code"] == "INMUN"
        assert abs(mun["lat"] - 22.8396) < 0.1

        # Hamad Port
        hmd = match_location("HAMAD, QA", "SEA")
        assert hmd is not None
        assert hmd["matched_code"] == "QAHMD"

        # Terminal facility substring
        terminal_match = match_location("Adani Mundra Container Terminal 2", "SEA")
        assert terminal_match is not None
        assert terminal_match["matched_code"] == "INMUN"

        # Ennore facility
        ennore_match = match_location("Tiruvallur/Adani Ennore Container Terminal | Kamarajar Port, Ennore", "SEA")
        assert ennore_match is not None
        assert ennore_match["matched_code"] == "INENR"

    def test_invalid_and_empty_inputs(self):
        assert match_location(None) is None
        assert match_location("") is None
        assert match_location("UNKNOWN") is None
        assert match_location("PORT / TERMINAL") is None
        assert match_location("   ") is None

    def test_database_persistence_with_coordinates(self):
        db = db_session.SessionLocal()
        try:
            # Verify location_coordinates master table is populated
            count = db.query(LocationCoordinate).count()
            assert count >= 6000

            # Test save_snapshot with station coordinates
            test_num = "TEST-COORD-99999"
            shipment = DatabasePersistenceTool.save_snapshot(
                db=db,
                tracking_number=test_num,
                transport_mode="SEA",
                carrier_code="MSCU",
                carrier_name="MSC",
                status="IN_TRANSIT",
                origin="MUNDRA, IN",
                destination="HAMAD, QA",
                pieces=1,
                weight_val=22000.0,
                weight_unit="kg",
                volume=None,
                provider_used="msc_direct_api",
                events=[
                    {
                        "station": "VISAKHAPATNAM, IN (INVTZ)",
                        "status_code": "LOAD",
                        "status_message": "Loaded on vessel",
                        "event_time": "2026-10-20T10:00:00Z",
                    },
                    {
                        "station": "ANTWERP, BE (BEANR)",
                        "status_code": "DISCH",
                        "status_message": "Discharged from vessel",
                        "event_time": "2026-10-25T14:30:00Z",
                    },
                ],
                raw_data={},
                attempts=[],
            )

            # Assert shipment origin/destination coordinates
            assert shipment.origin_lat is not None
            assert shipment.origin_code == "INMUN"
            assert shipment.destination_lat is not None
            assert shipment.destination_code == "QAHMD"

            # Assert event coordinates
            events = db.query(TrackingEvent).filter(TrackingEvent.shipment_id == shipment.id).all()
            assert len(events) == 2
            vtz_ev = next(e for e in events if "INVTZ" in (e.location_code or ""))
            assert vtz_ev.latitude is not None
            assert vtz_ev.longitude is not None
            assert abs(vtz_ev.latitude - 17.7) < 0.1

            anr_ev = next(e for e in events if "BEANR" in (e.location_code or ""))
            assert anr_ev.latitude is not None
            assert anr_ev.longitude is not None
            assert abs(anr_ev.latitude - 51.21667) < 0.1

        finally:
            db.close()

    def test_mobile_app_response_coordinates_serialization(self):
        resp = UnifiedTrackingResponse(
            tracking_number="160-12345678",
            mode="AIR",
            carrier=CarrierInfo(
                code="CATHAY",
                name="Cathay Cargo",
                mode="AIR",
                primary_provider="cathay_cargo",
            ),
            status="DELIVERED",
            origin="HKG",
            destination="BOM",
            origin_coordinates=LocationCoordinates(
                lat=22.31184,
                lng=113.914862,
                matched_code="HKG",
                matched_name="Hong Kong International Airport",
                location_type="AIRPORT",
            ),
            destination_coordinates=LocationCoordinates(
                lat=19.088699,
                lng=72.867897,
                matched_code="BOM",
                matched_name="Chhatrapati Shivaji Maharaj International Airport",
                location_type="AIRPORT",
            ),
            events=[
                UnifiedTrackingEvent(
                    station="HKG",
                    status_message="Departed Hong Kong",
                    coordinates=LocationCoordinates(
                        lat=22.31184,
                        lng=113.914862,
                        matched_code="HKG",
                        matched_name="Hong Kong International Airport",
                        location_type="AIRPORT",
                    ),
                )
            ],
            agent_trail=AgentDecisionTrail(
                detected_mode="AIR",
                carrier_identified="Cathay Cargo",
                carrier_code="CATHAY",
                provider_plan=["cathay_cargo"],
            ),
        )

        mobile_dict = to_mobile_app_response(resp)
        assert mobile_dict["originCoordinates"] is not None
        assert mobile_dict["originCoordinates"]["lat"] == 22.31184
        assert mobile_dict["events"][0]["lat"] == 22.31184
        assert mobile_dict["events"][0]["lng"] == 113.914862
        assert mobile_dict["events"][0]["locationName"] == "Hong Kong International Airport"
