import pytest
from app.core.identifier import parse_and_identify
from app.agents.routing_agent import RoutingAgent
from app.agents.tracking_agent import TrackingOrchestratorAgent
from app.db.session import init_db_engine, get_session


@pytest.fixture(scope="module")
def db_session():
    init_db_engine()
    session = get_session()
    yield session
    session.close()


def test_identifier_air_160():
    res = parse_and_identify("16015246221")
    assert res.mode == "AIR"
    assert res.prefix == "160"
    assert res.serial_number == "15246221"
    assert res.clean_tracking_number == "160-15246221"
    assert res.carrier_code == "CX"
    assert res.carrier_name == "Cathay Pacific Cargo"
    assert res.primary_provider == "cathay_cargo"
    assert "generic_air" in res.fallback_providers


def test_identifier_sea_maersk():
    res = parse_and_identify("MAEU1234567")
    assert res.mode == "SEA"
    assert res.prefix == "MAEU"
    assert res.carrier_code == "MSK"
    assert res.primary_provider == "maersk"
    assert "ldb_container" in res.fallback_providers


def test_identifier_sea_msc():
    msc_prefixes = ["MEDU", "MSCU", "MSDU", "MSMU", "MSNU"]
    for prefix in msc_prefixes:
        res = parse_and_identify(f"{prefix}9876543")
        assert res.mode == "SEA"
        assert res.prefix == prefix
        assert res.carrier_code == "MSC"
        assert res.carrier_name == "Mediterranean Shipping Company"
        assert res.primary_provider == "msc"
        assert res.is_supported is True


def test_msc_provider_tracking_url():
    from app.providers.sea.msc import MSC_TRACKING_URL, MscProvider
    assert MSC_TRACKING_URL == "https://www.msc.com/api/feature/tools/TrackingInfo"
    provider = MscProvider()
    assert provider.name == "msc"


@pytest.mark.asyncio
async def test_agent_tracking_flow_air(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="16015246221",
        db=db_session,
    )
    assert response.mode == "AIR"
    assert response.carrier.code == "CX"
    assert response.carrier.prefix == "160"
    assert response.status != "UNKNOWN"
    assert len(response.agent_trail.attempts) >= 1
    assert response.agent_trail.final_provider_used in ("cathay_cargo", "db_cache (cathay_cargo)")


@pytest.mark.asyncio
async def test_agent_tracking_singapore_airlines(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="618-57062924",
        db=db_session,
    )
    assert response.mode == "AIR"
    assert response.carrier.prefix == "618"
    assert response.agent_trail.final_provider_used == "singapore_airlines"
    assert response.origin == "TFU"
    assert response.destination == "BOM"


@pytest.mark.asyncio
async def test_agent_tracking_jal_cargo(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="131-80969700",
        db=db_session,
    )
    assert response.mode == "AIR"
    assert response.carrier.prefix == "131"
    assert response.agent_trail.final_provider_used == "jal_cargo"
    assert response.origin == "ICN"
    assert response.destination == "BLR"
    assert response.pieces == 2
    assert response.weight["value"] == 281.0
    assert response.status == "Delivered"


@pytest.mark.asyncio
async def test_agent_tracking_unsupported_airline(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="01699887766",
        db=db_session,
    )
    assert response.mode == "AIR"
    assert response.status == "AIRLINE_NOT_SUPPORTED"
    assert "Airline not supported" in response.message
    assert len(response.events) == 0


@pytest.mark.asyncio
async def test_agent_tracking_unsupported_shipping_line(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="HLCU1234567",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.status == "SHIPPING_LINE_NOT_SUPPORTED"
    assert "Shipping line not supported" in response.message
    assert len(response.events) == 0


@pytest.mark.asyncio
async def test_agent_tracking_sea_msc(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="MSMU6484830",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "MSC"
    assert response.agent_trail.final_provider_used == "msc"
    assert response.origin == "MUNDRA, IN"
    assert response.destination == "HAMAD, QA"
    assert response.status == "Delivered"
    assert len(response.events) > 0


@pytest.mark.asyncio
async def test_agent_tracking_invalid_format(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="invalid_awb_123",
        db=db_session,
    )
    assert response.status == "INVALID_TRACKING_NUMBER"
    assert "Invalid tracking number format" in response.message
    assert len(response.events) == 0


@pytest.mark.asyncio
async def test_agent_tracking_not_found(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="MSMU0000000",
        db=db_session,
    )
    assert response.status == "NOT_FOUND"
    assert "Tracking not found" in response.message
    assert len(response.events) == 0


def test_identifier_sea_one():
    res = parse_and_identify("ONEU1897419")
    assert res.mode == "SEA"
    assert res.carrier_code == "ONE"
    assert res.prefix == "ONEU"
    assert res.primary_provider == "one_line"
    assert "ldb_container" in res.fallback_providers
    assert res.is_supported is True


@pytest.mark.asyncio
async def test_agent_tracking_sea_one_ldb(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="ONEU1897419",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "ONE"
    assert response.agent_trail.final_provider_used in ("one_line", "ldb_container")
    assert response.status != "NOT_SUPPORTED"
    assert "Shipment tracked successfully" in response.message


def test_identifier_sea_mrsu_maersk():
    res = parse_and_identify("MRSU0229101")
    assert res.mode == "SEA"
    assert res.carrier_code == "MSK"
    assert res.prefix == "MRSU"
    assert res.primary_provider == "maersk"
    assert "ldb_container" in res.fallback_providers
    assert res.is_supported is True


def test_identifier_sea_hasu_maersk():
    res = parse_and_identify("HASU4935791")
    assert res.mode == "SEA"
    assert res.carrier_code == "MSK"
    assert res.prefix == "HASU"
    assert res.primary_provider == "maersk"
    assert "ldb_container" in res.fallback_providers
    assert res.is_supported is True


@pytest.mark.asyncio
async def test_agent_tracking_sea_mrsu_maersk_ldb(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="MRSU0229101",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "MSK"
    assert response.agent_trail.final_provider_used == "ldb_container"
    assert response.status == "In Transit"
    assert len(response.events) > 0
    assert "Shipment tracked successfully via Maersk Line" in response.message


@pytest.mark.asyncio
async def test_agent_tracking_sea_msc_medu(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="MEDU9650838",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "MSC"
    assert response.agent_trail.final_provider_used in ("msc", "db_cache (msc)")
    assert response.status in ("Delivered", "In Transit")
    assert len(response.events) > 0


@pytest.mark.asyncio
async def test_agent_tracking_sea_msc_msdu(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="MSDU9793707",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "MSC"
    assert response.agent_trail.final_provider_used in ("msc", "db_cache (msc)")
    assert response.status in ("Delivered", "In Transit")
    assert len(response.events) > 0



