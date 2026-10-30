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
    assert response.agent_trail.final_provider_used in ("singapore_airlines", "db_cache (singapore_airlines)")
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
    assert response.agent_trail.final_provider_used in ("jal_cargo", "db_cache (jal_cargo)")
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
async def test_agent_tracking_containertracking_net_hlcu(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="HLCU1234567",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.name == "Hapag-Lloyd"
    assert response.agent_trail.final_provider_used in ("hapag_lloyd", "containertracking_net", "generic_ocean")
    assert response.status == "In Transit"
    assert len(response.events) > 0
    assert response.raw_data.get("modal_popup") is not None


@pytest.mark.asyncio
async def test_agent_tracking_sea_msc(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="MSMU6484830",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "MSC"
    assert response.agent_trail.final_provider_used in ("msc", "db_cache (msc)", "generic_ocean")
    if response.agent_trail.final_provider_used in ("msc", "db_cache (msc)"):
        assert response.origin == "MUNDRA, IN"
        assert response.destination == "HAMAD, QA"
    assert response.status in ("Delivered", "In Transit")
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
    assert response.status in ("NOT_FOUND", "PROVIDER_ERROR")
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
    assert response.agent_trail.final_provider_used in ("one_line", "ldb_container", "generic_ocean")
    assert response.status != "NOT_SUPPORTED"
    assert "Shipment tracked successfully" in response.message


@pytest.mark.asyncio
async def test_agent_tracking_sea_one_cop_events(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="ONEU5436776",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "ONE"
    assert response.agent_trail.final_provider_used in ("one_line", "ldb_container", "generic_ocean")
    assert response.status != "NOT_SUPPORTED"


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
    assert res.carrier_name == "Maersk Line"
    assert res.prefix == "HASU"
    assert res.primary_provider == "maersk"
    assert "track_trace" in res.fallback_providers
    assert "ldb_container" in res.fallback_providers
    assert res.is_supported is True


def test_identifier_hasu4644219_routing_and_fallback_queue():
    res = parse_and_identify("HASU4644219")
    assert res.mode == "SEA"
    assert res.carrier_code == "MSK"
    assert res.carrier_name == "Maersk Line"
    assert res.prefix == "HASU"
    assert res.primary_provider == "maersk"
    assert res.fallback_providers == ["track_trace", "ldb_container", "generic_ocean"]
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
    assert response.agent_trail.final_provider_used in ("maersk", "ldb_container", "db_cache (maersk)", "generic_ocean")
    assert response.status == "In Transit"
    assert len(response.events) > 0
    assert "Shipment tracked successfully" in response.message


@pytest.mark.asyncio
async def test_agent_tracking_sea_msc_medu(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="MEDU9650838",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.code == "MSC"
    assert response.agent_trail.final_provider_used in ("msc", "db_cache (msc)", "generic_ocean")
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
    assert response.agent_trail.final_provider_used in ("msc", "db_cache (msc)", "generic_ocean")
    assert response.status in ("Delivered", "In Transit")
    assert len(response.events) > 0


def test_identifier_containertracking_net_prefixes():
    # Test sample prefixes from containertracking.net prefix registry
    # Carrier-owned prefixes
    carrier_samples = [
        ("COSU6123456", "COSCO", "containertracking_net"),
        ("ZIMU1234567", "ZIM", "containertracking_net"),
        ("YMLU1234567", "YANG-MING", "containertracking_net"),
    ]
    for q, expected_carrier_code, expected_provider in carrier_samples:
        res = parse_and_identify(q)
        assert res.mode == "SEA"
        assert res.carrier_code == expected_carrier_code
        assert res.primary_provider == expected_provider
        assert res.is_supported is True
        assert "generic_ocean" in res.fallback_providers

    # Leasing company prefixes (Triton, Textainer, etc.) route to one_line first to catch active voyages
    leasing_samples = [
        ("TRHU4047237", "TRITON", "one_line"),
        ("TEMU1234567", "TEXTAINER", "one_line"),
    ]
    for q, expected_carrier_code, expected_provider in leasing_samples:
        res = parse_and_identify(q)
        assert res.mode == "SEA"
        assert res.carrier_code == expected_carrier_code
        assert res.primary_provider == expected_provider
        assert res.is_supported is True
        assert "containertracking_net" in res.fallback_providers
        assert "generic_ocean" in res.fallback_providers


@pytest.mark.asyncio
async def test_agent_tracking_containertracking_net_triton(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="TRHU4047237",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert "Triton" in response.carrier.name
    assert response.agent_trail.final_provider_used in ("one_line", "containertracking_net", "generic_ocean")
    if response.agent_trail.final_provider_used == "one_line":
        assert len(response.events) >= 10
        assert response.origin.city == "DA NANG"
        assert "LOS ANGELES" in response.destination.city
    else:
        # Fallback equipment verification when network is offline/sandboxed
        assert len(response.events) >= 2
    modal = response.raw_data.get("modal_popup")
    assert modal is not None
    assert "https://containertracking.net" in modal["containertracking_url"]


def test_identifier_hapag_lloyd_dayu():
    res = parse_and_identify("DAYU6129689")
    assert res.mode == "SEA"
    assert res.carrier_code == "HAPAG_LLOY"
    assert res.carrier_name == "Hapag-Lloyd"
    assert res.primary_provider == "hapag_lloyd"
    assert res.is_supported is True
    assert "ldb_container" in res.fallback_providers


@pytest.mark.asyncio
async def test_agent_tracking_hapag_lloyd_dayu(db_session):
    orchestrator = TrackingOrchestratorAgent()
    response = await orchestrator.execute_tracking(
        query="DAYU6129689",
        db=db_session,
    )
    assert response.mode == "SEA"
    assert response.carrier.name == "Hapag-Lloyd"
    assert response.carrier.code == "HAPAG_LLOY"
    assert response.agent_trail.final_provider_used in ("hapag_lloyd", "ldb_container", "generic_ocean")
    assert len(response.events) >= 2
    modal = response.raw_data.get("modal_popup")
    assert modal is not None
    assert "https://www.hapag-lloyd.com/solutions/tracking/#/DAYU6129689" in modal["official_tracking_url"]
    assert "https://containertracking.net" in modal["containertracking_url"]





