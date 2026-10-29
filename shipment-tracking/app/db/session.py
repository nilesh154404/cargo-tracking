import logging
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.db.models import Base, Carrier, SubscriptionTier, Tenant, User, ApiKey, LocationCoordinate
from app.core.security import hash_password, hash_api_key

logger = logging.getLogger("shipment_tracking.db")

engine = None
SessionLocal = None


def _auto_migrate(engine):
    """Automatically add new columns to existing SQLite/MySQL tables if missing."""
    with engine.begin() as conn:
        for col, col_type in [
            ("tenant_id", "INTEGER"),
            ("customer_reference", "VARCHAR(100)"),
            ("active_polling_enabled", "BOOLEAN DEFAULT 0"),
            ("last_polled_at", "DATETIME"),
            ("origin_lat", "FLOAT"),
            ("origin_lng", "FLOAT"),
            ("origin_code", "VARCHAR(50)"),
            ("origin_name", "VARCHAR(255)"),
            ("destination_lat", "FLOAT"),
            ("destination_lng", "FLOAT"),
            ("destination_code", "VARCHAR(50)"),
            ("destination_name", "VARCHAR(255)"),
            ("mawb_obl_no", "VARCHAR(100)"),
            ("hawb_hbl_no", "VARCHAR(100)"),
            ("vessel_name", "VARCHAR(150)"),
            ("flight_no", "VARCHAR(50)"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE shipments ADD COLUMN {col} {col_type}"))
            except Exception:
                pass

        for col, col_type in [
            ("latitude", "FLOAT"),
            ("longitude", "FLOAT"),
            ("location_code", "VARCHAR(50)"),
            ("location_name", "VARCHAR(255)"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE tracking_events ADD COLUMN {col} {col_type}"))
            except Exception:
                pass

        try:
            conn.execute(text("ALTER TABLE carriers MODIFY COLUMN prefix VARCHAR(500)"))
        except Exception:
            pass


def init_db_engine():
    global engine, SessionLocal
    mysql_url = settings.get_database_url
    try:
        logger.info(f"Connecting to MySQL database at {settings.MYSQL_HOST}:{settings.MYSQL_PORT} (DB: {settings.MYSQL_DATABASE})...")
        test_engine = create_engine(
            mysql_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={"connect_timeout": 3},
        )
        with test_engine.connect() as conn:
            pass
        engine = test_engine
        logger.info("Successfully connected to MySQL database!")
    except Exception as exc:
        if settings.AUTO_FALLBACK_SQLITE:
            logger.warning(
                f"Could not connect to MySQL ({exc}). Falling back to local SQLite at {settings.FALLBACK_SQLITE_URL}."
            )
            engine = create_engine(
                settings.FALLBACK_SQLITE_URL,
                connect_args={"check_same_thread": False},
            )
        else:
            raise exc

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    _auto_migrate(engine)
    
    session = SessionLocal()
    try:
        seed_default_subscription_tiers(session)
        seed_default_tenants(session)
        seed_default_carriers(session)
        try:
            from app.scripts.seed_locations import seed_locations_if_needed
            seed_locations_if_needed(force=False)
        except Exception as seed_err:
            logger.warning(f"Could not auto-seed location coordinates: {seed_err}")
    finally:
        session.close()

    return engine


def get_session() -> Session:
    global SessionLocal
    if SessionLocal is None:
        init_db_engine()
    return SessionLocal()


def seed_default_subscription_tiers(session: Session):
    """Seed public subscription plans."""
    tiers = [
        {
            "code": "developer",
            "name": "Developer (Free)",
            "monthly_credits": 100,
            "rate_limit_rpm": 10,
            "max_api_keys": 2,
            "allow_batch": False,
            "allow_webhooks": True,
            "allow_custom_carriers": False,
            "price_usd_monthly": 0.0,
        },
        {
            "code": "growth",
            "name": "Growth Tier",
            "monthly_credits": 2500,
            "rate_limit_rpm": 60,
            "max_api_keys": 10,
            "allow_batch": True,
            "allow_webhooks": True,
            "allow_custom_carriers": False,
            "price_usd_monthly": 199.0,
        },
        {
            "code": "business",
            "name": "Business Tier",
            "monthly_credits": 15000,
            "rate_limit_rpm": 300,
            "max_api_keys": 25,
            "allow_batch": True,
            "allow_webhooks": True,
            "allow_custom_carriers": True,
            "price_usd_monthly": 699.0,
        },
        {
            "code": "enterprise",
            "name": "Enterprise Tier",
            "monthly_credits": 1000000,
            "rate_limit_rpm": 1200,
            "max_api_keys": 100,
            "allow_batch": True,
            "allow_webhooks": True,
            "allow_custom_carriers": True,
            "price_usd_monthly": 2499.0,
        },
    ]
    try:
        for t in tiers:
            existing = session.execute(
                select(SubscriptionTier).where(SubscriptionTier.code == t["code"])
            ).scalar_one_or_none()
            if not existing:
                session.add(SubscriptionTier(**t))
            else:
                for k, v in t.items():
                    setattr(existing, k, v)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(f"Error seeding subscription tiers: {exc}")


def seed_default_tenants(session: Session):
    """Seed default enterprise organization, admin user, and initial API key."""
    try:
        tenant = session.execute(
            select(Tenant).where(Tenant.slug == settings.DEFAULT_TENANT_SLUG)
        ).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                slug=settings.DEFAULT_TENANT_SLUG,
                name=settings.DEFAULT_TENANT_NAME,
                tier_code="enterprise",
                monthly_quota=1000000,
                current_usage=0,
                rate_limit_rpm=1200,
                allow_overage=True,
                is_active=True,
            )
            session.add(tenant)
            session.flush()

        # Global Platform Superadmin accounts (no tenant)
        for sa_email in ["superadmin@cargotrack.io", "admin@cargotrack.io"]:
            sa_user = session.execute(
                select(User).where(User.email == sa_email)
            ).scalar_one_or_none()
            if not sa_user:
                sa_user = User(
                    tenant_id=None,
                    email=sa_email,
                    password_hash=hash_password("SuperAdmin@2026!Cargo"),
                    full_name="Global Platform Superadmin",
                    role="SUPER_ADMIN",
                    is_active=True,
                )
                session.add(sa_user)
            else:
                sa_user.role = "SUPER_ADMIN"
                sa_user.is_active = True
                sa_user.password_hash = hash_password("SuperAdmin@2026!Cargo")

        # Demo Organization Tenant Admin accounts
        for demo_email, demo_pwd in [
            ("admin@demologistics.com", "demo123"),
            ("admin@apexlogistics.com", "demo123"),
            ("admin@apex-logistics.test", "Password@2026!Secure"),
        ]:
            demo_user = session.execute(
                select(User).where(User.email == demo_email)
            ).scalar_one_or_none()
            if not demo_user:
                demo_user = User(
                    tenant_id=tenant.id,
                    email=demo_email,
                    password_hash=hash_password(demo_pwd),
                    full_name="Demo Organization Admin",
                    role="ADMIN",
                    is_active=True,
                )
                session.add(demo_user)
            else:
                demo_user.is_active = True
                demo_user.password_hash = hash_password(demo_pwd)

        demo_key = "cargotrk_live_defaultdemo00000000000000000"
        demo_key_hash = hash_api_key(demo_key)
        existing_key = session.execute(
            select(ApiKey).where(ApiKey.key_hash == demo_key_hash)
        ).scalar_one_or_none()
        if not existing_key:
            api_key_obj = ApiKey(
                tenant_id=tenant.id,
                name="Default Demo Master Key",
                key_prefix=demo_key[:18],
                key_hash=demo_key_hash,
                scopes="tracking:live,tracking:read,shipments:batch,webhooks:write,admin:manage",
                is_active=True,
            )
            session.add(api_key_obj)

        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(f"Error seeding default tenant/admin: {exc}")


def seed_default_carriers(session: Session):
    """Seed supported air and sea carriers."""
    carriers_data = [
        # AIR CARRIERS
        {
            "code": "CX",
            "prefix": "160",
            "name": "Cathay Pacific Cargo",
            "mode": "AIR",
            "primary_provider": "cathay_cargo",
            "fallback_providers": "generic_air",
        },
        {
            "code": "EK",
            "prefix": "176",
            "name": "Emirates SkyCargo",
            "mode": "AIR",
            "primary_provider": "emirates_skycargo",
            "fallback_providers": "generic_air",
        },
        {
            "code": "SQ",
            "prefix": "618",
            "name": "Singapore Airlines Cargo",
            "mode": "AIR",
            "primary_provider": "singapore_airlines",
            "fallback_providers": "generic_air",
        },
        {
            "code": "LH",
            "prefix": "020",
            "name": "Lufthansa Cargo",
            "mode": "AIR",
            "primary_provider": "lufthansa_cargo",
            "fallback_providers": "generic_air",
        },
        {
            "code": "JL",
            "prefix": "131",
            "name": "Japan Airlines Cargo",
            "mode": "AIR",
            "primary_provider": "jal_cargo",
            "fallback_providers": "generic_air",
        },
        {
            "code": "MSK",
            "prefix": "MAEU,MRSU,MSKU,MRKU,HASU,SUDU",
            "name": "Maersk Line",
            "mode": "SEA",
            "primary_provider": "maersk",
            "fallback_providers": "track_trace,ldb_container,generic_ocean",
        },
        {
            "code": "MSC",
            "prefix": "MSCU,MSMU,MEDU,MSDU,MSNU",
            "name": "Mediterranean Shipping Company",
            "mode": "SEA",
            "primary_provider": "msc",
            "fallback_providers": "generic_ocean",
        },
        {
            "code": "ONE",
            "prefix": "ONEU,ONEY",
            "name": "Ocean Network Express (ONE)",
            "mode": "SEA",
            "primary_provider": "one_line",
            "fallback_providers": "ldb_container,generic_ocean",
        },
    ]

    try:
        for c in carriers_data:
            existing = session.execute(
                select(Carrier).where(Carrier.code == c["code"])
            ).scalar_one_or_none()
            if not existing:
                carrier = Carrier(**c)
                session.add(carrier)
            else:
                existing.prefix = c["prefix"]
                existing.primary_provider = c["primary_provider"]
                existing.fallback_providers = c["fallback_providers"]
                existing.name = c["name"]
        session.commit()

        # Dynamically seed all ocean container carriers from PREFIX_DB
        try:
            from app.core.container_prefixes_data import PREFIX_DB
            from collections import defaultdict
            carrier_groups = defaultdict(lambda: {"prefixes": [], "slug": ""})
            for pfx, info in PREFIX_DB.items():
                c_name = info.get("carrier") or f"Shipping Line ({pfx})"
                slug = (info.get("slug") or pfx.lower()).upper().replace("-", "_")[:10]
                carrier_groups[c_name]["prefixes"].append(pfx)
                if not carrier_groups[c_name]["slug"]:
                    carrier_groups[c_name]["slug"] = slug

            for c_name, grp in carrier_groups.items():
                code = grp["slug"]
                if code in ("MSK", "MSC", "ONE", "MAERSK"):
                    continue
                prefixes_str = ",".join(sorted(grp["prefixes"]))[:500]
                existing = session.execute(
                    select(Carrier).where(Carrier.code == code)
                ).scalar_one_or_none()
                if not existing:
                    carrier = Carrier(
                        code=code,
                        prefix=prefixes_str,
                        name=c_name,
                        mode="SEA",
                        primary_provider="containertracking_net",
                        fallback_providers="generic_ocean",
                    )
                    session.add(carrier)
                else:
                    existing.prefix = prefixes_str
            session.commit()
        except Exception as exc:
            logger.warning(f"Error seeding extended ocean carriers: {exc}")
    except Exception as exc:
        session.rollback()
        logger.error(f"Error seeding carriers: {exc}")


def get_db():
    if SessionLocal is None:
        init_db_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
