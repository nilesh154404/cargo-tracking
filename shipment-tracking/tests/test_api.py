from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "supported_modes" in data
    assert "AIR" in data["supported_modes"]
    assert "SEA" in data["supported_modes"]


def test_api_carriers():
    response = client.get("/api/v1/carriers")
    assert response.status_code == 200
    carriers = response.json()
    assert len(carriers) >= 4
    codes = [c["code"] for c in carriers]
    assert "CX" in codes
    assert "EK" in codes
    assert "SQ" in codes
    assert "MSK" in codes


def test_api_providers_list_and_health():
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    providers = response.json()
    names = [p["name"] for p in providers]
    assert "cathay_cargo" in names
    assert "emirates_skycargo" in names
    assert "singapore_airlines" in names
    assert "lufthansa_cargo" in names
    assert "maersk" in names
    assert "msc" in names

    health = client.get("/api/v1/providers/health")
    assert health.status_code == 200
    h_data = health.json()
    assert h_data["total_providers"] >= 6


def test_api_upsert_carrier_dynamic():
    new_carrier = {
        "code": "AF",
        "prefix": "057",
        "name": "Air France Cargo",
        "mode": "AIR",
        "primary_provider": "generic_air",
        "fallback_providers": [],
    }
    resp = client.post("/api/v1/carriers", json=new_carrier)
    assert resp.status_code == 200
    data = resp.json()
    assert data["carrier"]["code"] == "AF"

    get_resp = client.get("/api/v1/carriers/AF")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Air France Cargo"


def test_api_track_air_post():
    payload = {"query": "16015246221"}
    response = client.post("/api/v1/track", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "AIR"
    assert data["tracking_number"] == "160-15246221"
    assert data["carrier"]["code"] == "CX"
    assert data["agent_trail"]["carrier_code"] == "CX"
    assert data["agent_trail"]["final_provider_used"] == "cathay_cargo"


def test_api_track_path_based():
    response = client.get("/api/v1/track/160-15245974")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "AIR"
    assert data["tracking_number"] == "160-15245974"
    assert data["carrier"]["code"] == "CX"
    assert data["status"] == "Delivered"


def test_api_track_sea_get():
    response = client.get("/api/v1/track?query=MSMU6484830")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "SEA"
    assert data["carrier"]["code"] == "MSC"
    assert data["agent_trail"]["final_provider_used"] == "msc"
    assert data["status"] == "Delivered"


def test_api_history_auto_track():
    response = client.get("/api/v1/history/MSMU6484830")
    assert response.status_code == 200
    hist = response.json()
    assert hist["mode"] == "SEA"
    assert hist["carrier_code"] == "MSC"
    assert len(hist["events"]) >= 1


def test_api_cathay_token_direct():
    response = client.get("/api/v1/cathay/token")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
