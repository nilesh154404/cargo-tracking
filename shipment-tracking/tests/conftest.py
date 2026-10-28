import os
import shutil
import pytest
from app.config import settings

MAIN_DB_FILE = "shipment_tracking.db"
TEST_DB_FILE = "test_shipment_tracking.db"

# Force test execution on an isolated database copy
if os.path.exists(MAIN_DB_FILE):
    shutil.copy(MAIN_DB_FILE, TEST_DB_FILE)

settings.FALLBACK_SQLITE_URL = f"sqlite:///./{TEST_DB_FILE}"
settings.AUTO_FALLBACK_SQLITE = True

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    from app.db.session import init_db_engine
    init_db_engine()
    yield
    # Clean up temporary test database copy
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass
