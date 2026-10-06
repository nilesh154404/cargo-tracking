import logging
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.db.models import Base, Carrier

logger = logging.getLogger("shipment_tracking.db")

engine = None
SessionLocal = None


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
    seed_default_carriers()
    return engine


def get_session() -> Session:
    global SessionLocal
    if SessionLocal is None:
        init_db_engine()
    return SessionLocal()


def seed_default_carriers():
    """Seed supported air and sea carriers."""
    if not SessionLocal:
        return

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
            "prefix": "MAEU,MRSU,MSKU",
            "name": "Maersk Line",
            "mode": "SEA",
            "primary_provider": "ldb_container",
            "fallback_providers": "generic_ocean",
        },
        {
            "code": "MSC",
            "prefix": "MSCU,MSMU,MEDU",
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
            "primary_provider": "ldb_container",
            "fallback_providers": "generic_ocean",
        },
    ]

    session: Session = SessionLocal()
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
    except Exception as exc:
        session.rollback()
        logger.error(f"Error seeding carriers: {exc}")
    finally:
        session.close()


def get_db():
    if SessionLocal is None:
        init_db_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
