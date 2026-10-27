import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_session
from app.db.models import Tenant

client = TestClient(app)


def test_enterprise_root_discovery():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "2.0.0"
    assert "cargotrk_live_" in data["authentication"]["api_key_header"]
    assert "demo_master_key" in data["authentication"]


def test_subscription_plans_endpoint():
    response = client.get("/api/v1/subscription/plans")
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) >= 4
    codes = [p["code"] for p in plans]
    assert "developer" in codes
    assert "growth" in codes
    assert "business" in codes
    assert "enterprise" in codes


def test_organization_registration_and_api_key_lifecycle():
    uid = uuid.uuid4().hex[:8]
    slug = f"apex-{uid}"
    email = f"admin-{uid}@apex.test"

    # 1. Register new organization
    reg_payload = {
        "name": "Apex Global Freight Test",
        "slug": slug,
        "email": email,
        "password": "Password@2026!Secure",
        "full_name": "Apex Administrator",
        "tier_code": "growth",
    }
    response = client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["tenant"]["slug"] == slug
    assert data["tenant"]["tier"] == "growth"
    assert data["tenant"]["monthly_credits"] == 2500

    api_key_info = data["api_key"]
    secret_key = api_key_info["key"]
    assert secret_key.startswith("cargotrk_live_")
    jwt_access_token = data["tokens"]["access_token"]

    # 2. Login with credentials
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@2026!Secure"})
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data

    # 3. Access profile with JWT
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jwt_access_token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["tenant"]["slug"] == slug
    assert me_data["user"]["email"] == email

    # 4. Access profile with API Key
    key_me_resp = client.get("/api/v1/auth/me", headers={"X-API-Key": secret_key})
    assert key_me_resp.status_code == 200
    key_me_data = key_me_resp.json()
    assert key_me_data["auth_type"] == "API_KEY"
    assert key_me_data["tenant"]["slug"] == slug

    # 5. Create a secondary scoped API key
    new_key_resp = client.post(
        "/api/v1/api-keys",
        headers={"X-API-Key": secret_key},
        json={
            "name": "Staging ERP Integration Key",
            "scopes": ["tracking:live", "tracking:read"],
        },
    )
    assert new_key_resp.status_code == 200
    secondary_key = new_key_resp.json()["key"]
    secondary_key_id = new_key_resp.json()["id"]

    # 6. List API keys
    list_keys_resp = client.get("/api/v1/api-keys", headers={"X-API-Key": secret_key})
    assert list_keys_resp.status_code == 200
    keys_list = list_keys_resp.json()
    assert len(keys_list) >= 2

    # 7. Revoke the secondary API key
    del_resp = client.delete(f"/api/v1/api-keys/{secondary_key_id}", headers={"X-API-Key": secret_key})
    assert del_resp.status_code == 200

    # 8. Verifying revoked key is rejected with 401
    revoked_call = client.get("/api/v1/auth/me", headers={"X-API-Key": secondary_key})
    assert revoked_call.status_code == 401


def test_api_key_tracking_and_quota_metering():
    uid = uuid.uuid4().hex[:8]
    slug = f"metering-{uid}"
    email = f"ops-{uid}@metering.test"

    reg_payload = {
        "name": "Metering Test Organization",
        "slug": slug,
        "email": email,
        "password": "Password@2026!Secure",
        "tier_code": "developer",
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    api_key = reg_resp.json()["api_key"]["key"]

    # Check initial usage
    usage_resp = client.get("/api/v1/subscription/usage", headers={"X-API-Key": api_key})
    assert usage_resp.status_code == 200
    initial_usage = usage_resp.json()["current_usage"]
    assert initial_usage == 0
    assert usage_resp.json()["monthly_quota"] == 100

    # Execute a live tracking request with Bearer API Key header
    track_resp = client.post(
        "/api/v1/track",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": "MSMU6484830", "customer_reference": f"PO-{uid}"},
    )
    assert track_resp.status_code == 200
    assert track_resp.json()["status"] == "Delivered"

    # Verify credit deducted
    usage_after = client.get("/api/v1/subscription/usage", headers={"X-API-Key": api_key}).json()
    assert usage_after["current_usage"] == initial_usage + 1
    assert usage_after["remaining_credits"] == 99

    # Verify shipment is visible in tenant's shipment portfolio
    shipments_resp = client.get("/api/v1/shipments", headers={"X-API-Key": api_key})
    assert shipments_resp.status_code == 200
    shipments = shipments_resp.json()
    assert len(shipments) >= 1
    tracked_num = shipments[0]["tracking_number"]
    assert tracked_num == "MSMU6484830"
    assert shipments[0]["customer_reference"] == f"PO-{uid}"


def test_quota_cap_and_plan_upgrade():
    uid = uuid.uuid4().hex[:8]
    slug = f"cap-{uid}"
    email = f"billing-{uid}@captest.io"

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Cap Test Org",
            "slug": slug,
            "email": email,
            "password": "Password@2026!Secure",
            "tier_code": "developer",
        },
    )
    assert reg_resp.status_code == 201
    api_key = reg_resp.json()["api_key"]["key"]

    # Set usage = 100 (quota limit reached)
    session = get_session()
    tenant = session.query(Tenant).filter(Tenant.slug == slug).first()
    tenant.current_usage = 100
    tenant.monthly_quota = 100
    tenant.allow_overage = False
    session.commit()
    session.close()

    # Attempt tracking when quota exhausted -> Expect HTTP 429
    track_resp = client.post(
        "/api/v1/track",
        headers={"X-API-Key": api_key},
        json={"query": "MSMU6484830"},
    )
    assert track_resp.status_code == 429
    err = track_resp.json()["detail"]
    assert err["code"] == "quota_exceeded"

    # Upgrade to Business tier (15,000 quota)
    upgrade_resp = client.post(
        "/api/v1/subscription/upgrade",
        headers={"X-API-Key": api_key},
        json={"tier_code": "business"},
    )
    assert upgrade_resp.status_code == 200
    assert upgrade_resp.json()["monthly_quota"] == 15000

    # Tracking should now succeed immediately
    retry_track = client.post(
        "/api/v1/track",
        headers={"X-API-Key": api_key},
        json={"query": "MSMU6484830"},
    )
    assert retry_track.status_code == 200


def test_tenant_data_isolation():
    uid_a = uuid.uuid4().hex[:8]
    uid_b = uuid.uuid4().hex[:8]

    # Register Tenant A
    res_a = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Tenant Alpha {uid_a}",
            "slug": f"tenant-alpha-{uid_a}",
            "email": f"admin-{uid_a}@alpha.com",
            "password": "Password@2026!Secure",
        },
    ).json()
    key_a = res_a["api_key"]["key"]

    # Register Tenant B
    res_b = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Tenant Beta {uid_b}",
            "slug": f"tenant-beta-{uid_b}",
            "email": f"admin-{uid_b}@beta.com",
            "password": "Password@2026!Secure",
        },
    ).json()
    key_b = res_b["api_key"]["key"]

    # Tenant A creates an API key
    key_create_a = client.post(
        "/api/v1/api-keys",
        headers={"X-API-Key": key_a},
        json={"name": "Alpha Private Key"},
    ).json()
    alpha_key_id = key_create_a["id"]

    # Tenant B lists API keys -> Should NOT see Tenant A's key
    beta_keys = client.get("/api/v1/api-keys", headers={"X-API-Key": key_b}).json()
    beta_key_ids = [k["id"] for k in beta_keys]
    assert alpha_key_id not in beta_key_ids

    # Tenant B tries to delete Tenant A's key -> Expect 404
    hack_del = client.delete(f"/api/v1/api-keys/{alpha_key_id}", headers={"X-API-Key": key_b})
    assert hack_del.status_code == 404


def test_batch_tracking_endpoint():
    uid = uuid.uuid4().hex[:8]
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Batch Corp {uid}",
            "slug": f"batch-{uid}",
            "email": f"batch-{uid}@corp.test",
            "password": "Password@2026!Secure",
            "tier_code": "growth",
        },
    )
    assert reg_resp.status_code == 201
    api_key = reg_resp.json()["api_key"]["key"]

    batch_payload = {
        "items": [
            {"query": "MSMU6484830", "customer_reference": "REF-SEA-01"},
            {"query": "160-15246221", "customer_reference": "REF-AIR-02"},
        ]
    }

    batch_resp = client.post(
        "/api/v1/track/batch",
        headers={"X-API-Key": api_key},
        json=batch_payload,
    )
    assert batch_resp.status_code == 200
    data = batch_resp.json()
    assert data["total_requested"] == 2
    assert data["credits_consumed"] == 2
    assert len(data["results"]) == 2


def test_superadmin_onboard_tenant_and_ops():
    import uuid
    # 1. Superadmin Login
    superadmin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@cargotrack.io", "password": "SuperAdmin@2026!Cargo"}
    )
    assert superadmin_login.status_code == 200
    sa_token = superadmin_login.json()["access_token"]
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    # 2. Superadmin Onboards New Enterprise Tenant
    u_id = uuid.uuid4().hex[:8]
    onboard_payload = {
        "name": f"Nexus Global Freight {u_id}",
        "slug": f"nexus-{u_id}",
        "tier_code": "business",
        "admin_email": f"ops-{u_id}@nexus.io",
        "admin_password": "NexusOps@2026!Secure",
        "admin_name": "Nexus Operations Lead",
        "monthly_quota": 20000,
        "rate_limit_rpm": 400,
        "allow_overage": True
    }

    create_resp = client.post(
        "/api/v1/admin/tenants",
        headers=sa_headers,
        json=onboard_payload
    )
    assert create_resp.status_code == 200
    res_data = create_resp.json()
    assert res_data["tenant"]["slug"] == f"nexus-{u_id}"
    assert res_data["tenant"]["monthly_quota"] == 20000
    assert "secret_key" in res_data["api_key"]
    new_api_key = res_data["api_key"]["secret_key"]
    assert new_api_key.startswith("cargotrk_live_")

    # 3. New Tenant tracks cargo using generated API key
    track_resp = client.post(
        "/api/v1/track",
        headers={"X-API-Key": new_api_key},
        json={"query": "MSMU6484830"}
    )
    assert track_resp.status_code == 200
    assert track_resp.json()["tracking_number"] == "MSMU6484830"

    # 4. Superadmin Impersonates Tenant
    new_tenant_id = res_data["tenant"]["id"]
    imp_resp = client.post(
        f"/api/v1/admin/tenants/{new_tenant_id}/impersonate",
        headers=sa_headers
    )
    assert imp_resp.status_code == 200
    assert "access_token" in imp_resp.json()
    assert imp_resp.json()["tenant_slug"] == f"nexus-{u_id}"

    # 5. Superadmin checks Carrier Health SLA
    carrier_sla = client.get("/api/v1/admin/carriers", headers=sa_headers)
    assert carrier_sla.status_code == 200
    assert len(carrier_sla.json()) > 0
    assert "status" in carrier_sla.json()[0]

    # 6. Non-superadmin is blocked from admin onboarding (403 Forbidden)
    non_sa_resp = client.post(
        "/api/v1/admin/tenants",
        headers={"X-API-Key": new_api_key},
        json=onboard_payload
    )
    assert non_sa_resp.status_code == 403

