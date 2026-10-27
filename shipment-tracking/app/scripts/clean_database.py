import logging
from sqlalchemy import select, delete, text
from app.db.session import init_db_engine, get_session
from app.db.models import Tenant, User, ApiKey, Shipment, TrackingEvent, ProviderExecutionLog, UsageRecord
from app.core.security import hash_password, hash_api_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clean_database")

def clean_database():
    init_db_engine()
    db = get_session()

    try:
        logger.info("Starting database test pollution cleanup...")

        # 1. Ensure Tenant 1 (default-org) exists and is configured
        t1 = db.execute(select(Tenant).where(Tenant.slug == "default-org")).scalar_one_or_none()
        if not t1:
            t1 = Tenant(
                slug="default-org",
                name="Default Enterprise Logistics",
                tier_code="enterprise",
                monthly_quota=1000000,
                current_usage=7,
                rate_limit_rpm=1200,
                allow_overage=True,
                is_active=True,
            )
            db.add(t1)
            db.flush()
        else:
            t1.name = "Default Enterprise Logistics"
            t1.tier_code = "enterprise"
            t1.monthly_quota = 1000000
            t1.current_usage = 7
            t1.is_active = True

        # 2. Ensure Tenant 2 (apex-logistics) exists and is configured
        t2 = db.execute(select(Tenant).where(Tenant.slug == "apex-logistics")).scalar_one_or_none()
        if not t2:
            t2 = Tenant(
                slug="apex-logistics",
                name="Apex Global Freight & Logistics",
                tier_code="growth",
                monthly_quota=2500,
                current_usage=7,
                rate_limit_rpm=60,
                allow_overage=True,
                is_active=True,
            )
            db.add(t2)
            db.flush()
        else:
            t2.name = "Apex Global Freight & Logistics"
            t2.tier_code = "growth"
            t2.monthly_quota = 2500
            t2.current_usage = 7
            t2.is_active = True

        valid_tenant_ids = {t1.id, t2.id}

        # 3. Reassign real shipments to Tenant 1 and Tenant 2
        # Delete fake synthetic test shipments
        db.execute(delete(Shipment).where(Shipment.tracking_number.like("%TEST-%")))

        t1_trackings = {"160-15246221", "160-15245974", "MEDU9650838", "ONEYBLRG06172700", "ONEU2157736", "ONEU1728682", "MSMU6484830"}
        all_shipments = db.query(Shipment).all()
        for s in all_shipments:
            if s.tracking_number in t1_trackings:
                s.tenant_id = t1.id
            else:
                s.tenant_id = t2.id
        db.flush()

        # 4. Remove all test tenants not in valid_tenant_ids
        unwanted_tenants = db.query(Tenant).filter(~Tenant.id.in_(valid_tenant_ids)).all()
        logger.info(f"Removing {len(unwanted_tenants)} test/polluted tenants...")
        for ut in unwanted_tenants:
            db.delete(ut)
        db.flush()

        # 5. Ensure Superadmins (no tenant) exist with working credentials
        for sa_email in ["superadmin@cargotrack.io", "admin@cargotrack.io"]:
            sa_user = db.execute(select(User).where(User.email == sa_email)).scalar_one_or_none()
            if not sa_user:
                sa_user = User(
                    tenant_id=None,
                    email=sa_email,
                    password_hash=hash_password("SuperAdmin@2026!Cargo"),
                    full_name="Global Platform Superadmin",
                    role="SUPER_ADMIN",
                    is_active=True,
                )
                db.add(sa_user)
            else:
                sa_user.tenant_id = None
                sa_user.role = "SUPER_ADMIN"
                sa_user.is_active = True
                sa_user.password_hash = hash_password("SuperAdmin@2026!Cargo")

        # 6. Ensure Tenant 1 Admin
        u1 = db.execute(select(User).where(User.email == "admin@demologistics.com")).scalar_one_or_none()
        if not u1:
            u1 = User(
                tenant_id=t1.id,
                email="admin@demologistics.com",
                password_hash=hash_password("demo123"),
                full_name="Demo Organization Admin",
                role="ADMIN",
                is_active=True,
            )
            db.add(u1)
        else:
            u1.tenant_id = t1.id
            u1.role = "ADMIN"
            u1.is_active = True
            u1.password_hash = hash_password("demo123")

        # 7. Ensure Tenant 2 Admin
        u2 = db.execute(select(User).where(User.email == "admin@apexlogistics.com")).scalar_one_or_none()
        if not u2:
            u2 = User(
                tenant_id=t2.id,
                email="admin@apexlogistics.com",
                password_hash=hash_password("demo123"),
                full_name="Apex Logistics Admin",
                role="ADMIN",
                is_active=True,
            )
            db.add(u2)
        else:
            u2.tenant_id = t2.id
            u2.role = "ADMIN"
            u2.is_active = True
            u2.password_hash = hash_password("demo123")

        # Clean any remaining rogue users not attached to t1, t2, or superadmins
        valid_user_emails = {"superadmin@cargotrack.io", "admin@cargotrack.io", "admin@demologistics.com", "admin@apexlogistics.com"}
        rogue_users = db.query(User).filter(~User.email.in_(valid_user_emails)).all()
        logger.info(f"Removing {len(rogue_users)} rogue/test users...")
        for ru in rogue_users:
            db.delete(ru)

        # 8. Ensure API Keys for Tenant 1 and Tenant 2
        k1_secret = "cargotrk_live_defaultdemo00000000000000000"
        k1_hash = hash_api_key(k1_secret)
        k1 = db.execute(select(ApiKey).where(ApiKey.key_hash == k1_hash)).scalar_one_or_none()
        if not k1:
            k1 = ApiKey(
                tenant_id=t1.id,
                name="Default Demo Master Key",
                key_prefix=k1_secret[:18],
                key_hash=k1_hash,
                scopes="tracking:live,tracking:read,shipments:batch,webhooks:write,admin:manage",
                is_active=True,
            )
            db.add(k1)
        else:
            k1.tenant_id = t1.id

        k2_secret = "cargotrk_live_apexlogistics2026demo00000"
        k2_hash = hash_api_key(k2_secret)
        k2 = db.execute(select(ApiKey).where(ApiKey.key_hash == k2_hash)).scalar_one_or_none()
        if not k2:
            k2 = ApiKey(
                tenant_id=t2.id,
                name="Apex Logistics Production Key",
                key_prefix=k2_secret[:18],
                key_hash=k2_hash,
                scopes="tracking:live,tracking:read,shipments:batch",
                is_active=True,
            )
            db.add(k2)
        else:
            k2.tenant_id = t2.id

        # Delete any rogue API keys
        db.query(ApiKey).filter(~ApiKey.tenant_id.in_(valid_tenant_ids)).delete(synchronize_session=False)

        # 9. Clean execution logs of any orphaned shipments
        valid_shipment_ids = [s.id for s in db.query(Shipment).all()]
        db.query(TrackingEvent).filter(~TrackingEvent.shipment_id.in_(valid_shipment_ids)).delete(synchronize_session=False)

        db.commit()
        logger.info("Successfully cleaned database! Test pollution removed.")
        logger.info(f"Remaining Tenants: {db.query(Tenant).count()}")
        logger.info(f"Remaining Users: {db.query(User).count()}")
        logger.info(f"Remaining Shipments: {db.query(Shipment).count()}")
        logger.info(f"Remaining Tracking Events: {db.query(TrackingEvent).count()}")

    except Exception as exc:
        db.rollback()
        logger.error(f"Error during cleanup: {exc}")
        raise exc

if __name__ == "__main__":
    clean_database()
