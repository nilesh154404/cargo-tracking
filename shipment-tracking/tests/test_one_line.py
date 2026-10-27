import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.providers.sea.one_line import OneLineProvider
from app.schemas.tracking import TrackingInputRequest
from app.db.session import init_db_engine, get_session
from app.core.security import hash_api_key
from app.db.models import ApiKey

client = TestClient(app)

DEMO_API_KEY = "cargotrk_live_defaultdemo00000000000000000"


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    init_db_engine()
    db = get_session()
    try:
        key_hash = hash_api_key(DEMO_API_KEY)
        key_rec = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if not key_rec:
            key_rec = ApiKey(
                tenant_id=1,
                name="Test Master Key",
                key_prefix=DEMO_API_KEY[:18],
                key_hash=key_hash,
                scopes="tracking:live,tracking:read,shipments:batch,webhooks:write,admin:manage",
                is_active=True,
            )
            db.add(key_rec)
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Parameter Validation Tests (MAWB_OBL_NO / CONTAINER_NO requirement)
# ---------------------------------------------------------------------------

def test_validation_requires_mawb_or_container():
    """Verify that omitting both MAWB_OBL_NO and CONTAINER_NO raises validation error."""
    with pytest.raises(ValidationError) as exc:
        TrackingInputRequest(
            CARRIER_CODE="ONE",
            CARRIER_NAME="Ocean Network Express",
            VESSEL_NAME="X-PRESS KARAKORAM",
        )
    assert "Either MAWB_OBL_NO or CONTAINER_NO is required" in str(exc.value)


def test_validation_accepts_container_no_only():
    """Verify that providing only CONTAINER_NO passes validation."""
    req = TrackingInputRequest(CONTAINER_NO="ONEU2157736")
    assert req.CONTAINER_NO == "ONEU2157736"
    assert req.query == "ONEU2157736"


def test_validation_accepts_mawb_obl_no_only():
    """Verify that providing only MAWB_OBL_NO passes validation."""
    req = TrackingInputRequest(MAWB_OBL_NO="ONEYBLRG06172700")
    assert req.MAWB_OBL_NO == "ONEYBLRG06172700"
    assert req.query == "ONEYBLRG06172700"


def test_validation_accepts_all_7_parameters():
    """Verify that all 7 parameters are accepted and properly structured."""
    req = TrackingInputRequest(
        MAWB_OBL_NO="ONEYBLRG06172700",
        CONTAINER_NO="ONEU1728682",
        CARRIER_CODE="ONE",
        CARRIER_NAME="Ocean Network Express",
        VESSEL_NAME="X-PRESS KARAKORAM",
        HAWB_HBL_NO="HBL-992144",
        FLIGHT_NO="CX0802",
    )
    assert req.MAWB_OBL_NO == "ONEYBLRG06172700"
    assert req.CONTAINER_NO == "ONEU1728682"
    assert req.CARRIER_CODE == "ONE"
    assert req.CARRIER_NAME == "Ocean Network Express"
    assert req.VESSEL_NAME == "X-PRESS KARAKORAM"
    assert req.HAWB_HBL_NO == "HBL-992144"
    assert req.FLIGHT_NO == "CX0802"


# ---------------------------------------------------------------------------
# 2. OneLineProvider Direct Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_line_provider_container_search():
    """Test live ONE container search with ONEU2157736 (search_type CNTR_NO)."""
    provider = OneLineProvider()
    res = await provider.track(prefix="ONEU", serial="2157736", tracking_number="ONEU2157736")

    assert res.success is True
    assert res.provider_name == "one_line"
    assert res.pieces == 1
    assert len(res.events) > 0
    assert res.origin is not None or res.destination is not None
    # Verify cURL command was constructed
    assert res.request_curl is not None
    assert "ecomm.one-line.com" in res.request_curl
    assert "CNTR_NO" in res.request_curl


@pytest.mark.asyncio
async def test_one_line_provider_multi_container_booking_search():
    """Test live ONE booking search with ONEYBLRG06172700 (returns 5 containers)."""
    provider = OneLineProvider()
    res = await provider.track(prefix="ONEY", serial="BLRG06172700", tracking_number="ONEYBLRG06172700")

    assert res.success is True
    assert res.provider_name == "one_line"
    # Booking has 5 containers
    assert res.pieces == 5
    assert res.raw_data is not None
    assert "containers" in res.raw_data
    assert len(res.raw_data["containers"]) == 5
    container_numbers = [c["container_number"] for c in res.raw_data["containers"]]
    assert "ONEU1728682" in container_numbers
    # Verify total weight aggregated
    assert res.weight is not None
    assert res.weight["value"] > 40000
    # Verify events across containers
    assert len(res.events) >= 10


# ---------------------------------------------------------------------------
# 3. HTTP API Live Tracking Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_track_post_with_booking_multi_container():
    """Test POST /api/v1/track with ONE booking returning 5 containers."""
    payload = {
        "MAWB_OBL_NO": "ONEYBLRG06172700",
        "CARRIER_CODE": "ONE",
        "CARRIER_NAME": "Ocean Network Express",
    }
    response = client.post(
        "/api/v1/track",
        json=payload,
        headers={"X-API-Key": DEMO_API_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mode"] == "SEA"
    assert data["carrier"]["code"] == "ONE"
    assert data["pieces"] == 5
    assert "containers" in data
    assert data["containers"] is not None
    assert len(data["containers"]) == 5
    assert len(data["events"]) >= 5


def test_api_track_post_with_container_no():
    """Test POST /api/v1/track with ONE container number."""
    payload = {
        "CONTAINER_NO": "ONEU2157736",
        "CARRIER_CODE": "ONE",
    }
    response = client.post(
        "/api/v1/track",
        json=payload,
        headers={"X-API-Key": DEMO_API_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mode"] == "SEA"
    assert data["carrier"]["code"] == "ONE"
    assert len(data["events"]) > 0


def test_api_track_post_missing_both_required_params_fails():
    """Test POST /api/v1/track when omitting both MAWB_OBL_NO and CONTAINER_NO returns 422."""
    payload = {
        "CARRIER_CODE": "ONE",
        "CARRIER_NAME": "Ocean Network Express",
        "VESSEL_NAME": "X-PRESS KARAKORAM",
    }
    response = client.post(
        "/api/v1/track",
        json=payload,
        headers={"X-API-Key": DEMO_API_KEY},
    )
    assert response.status_code == 422
    assert "Either MAWB_OBL_NO or CONTAINER_NO is required" in response.text
