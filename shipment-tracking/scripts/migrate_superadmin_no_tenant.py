"""
Migration Script: Global Superadmin without Tenant (tenant_id = NULL)

Performs schema migration to ensure users.tenant_id is nullable,
and seeds/updates the global Superadmin account with no tenant binding.
"""
import os
import sys
import logging
from sqlalchemy import text, select
from sqlalchemy.orm import Session

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import init_db_engine, get_session
from app.db.models import User
from app.core.security import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration.superadmin")


def migrate_users_table_nullable_tenant(engine):
    """Ensure users.tenant_id allows NULL in SQLite or MySQL."""
    dialect_name = engine.dialect.name.lower()
    logger.info(f"Checking users table schema for dialect: {dialect_name}...")

    with engine.connect() as conn:
        if dialect_name == "sqlite":
            # Check current DDL of users table
            res = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users';")).scalar()
            if res and "tenant_id INTEGER NOT NULL" in res:
                logger.info("Migrating SQLite users table: making tenant_id nullable...")
                conn.execute(text("PRAGMA foreign_keys=off;"))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users_temp_migration (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER,
                        email VARCHAR(200) NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        full_name VARCHAR(150),
                        role VARCHAR(50) NOT NULL DEFAULT 'ADMIN',
                        is_active BOOLEAN DEFAULT 1,
                        last_login_at DATETIME,
                        created_at DATETIME,
                        FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
                    );
                """))
                conn.execute(text("""
                    INSERT INTO users_temp_migration (id, tenant_id, email, password_hash, full_name, role, is_active, last_login_at, created_at)
                    SELECT id, tenant_id, email, password_hash, full_name, role, is_active, last_login_at, created_at FROM users;
                """))
                conn.execute(text("DROP TABLE users;"))
                conn.execute(text("ALTER TABLE users_temp_migration RENAME TO users;"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users (tenant_id);"))
                conn.execute(text("PRAGMA foreign_keys=on;"))
                conn.commit()
                logger.info("SQLite users table migration completed successfully.")
            else:
                logger.info("SQLite users.tenant_id is already nullable.")
        elif dialect_name in ("mysql", "mariadb"):
            logger.info("Modifying MySQL users.tenant_id to be nullable...")
            conn.execute(text("ALTER TABLE users MODIFY tenant_id INT NULL;"))
            conn.commit()
            logger.info("MySQL users.tenant_id modified successfully.")


def seed_tenantless_superadmin(session: Session):
    """Seed or update global Superadmin user with tenant_id = None."""
    superadmin_credentials = [
        {
            "email": "superadmin@cargotrack.io",
            "password": "SuperAdmin@2026!Cargo",
            "full_name": "Global Platform Superadmin",
            "role": "SUPER_ADMIN",
            "tenant_id": None,
        },
        {
            "email": "admin@cargotrack.io",
            "password": "Admin@2026!Secure",
            "full_name": "Enterprise System Administrator",
            "role": "SUPER_ADMIN",
            "tenant_id": None,
        }
    ]

    for cred in superadmin_credentials:
        user = session.execute(
            select(User).where(User.email == cred["email"].lower())
        ).scalar_one_or_none()

        if user:
            user.role = "SUPER_ADMIN"
            user.tenant_id = None  # Detach from any tenant
            user.password_hash = hash_password(cred["password"])
            user.is_active = True
            session.commit()
            logger.info(f"Updated existing user '{cred['email']}' as global SUPER_ADMIN (no tenant).")
        else:
            new_user = User(
                email=cred["email"].lower(),
                password_hash=hash_password(cred["password"]),
                full_name=cred["full_name"],
                role="SUPER_ADMIN",
                tenant_id=None,  # No tenant
                is_active=True,
            )
            session.add(new_user)
            session.commit()
            logger.info(f"Created new global SUPER_ADMIN user '{cred['email']}' (no tenant).")

    print("\n" + "=" * 65)
    print("  SUPERADMIN ACCOUNTS READY (NO TENANT BINDING)")
    print("=" * 65)
    for cred in superadmin_credentials:
        print(f"  • Email:     {cred['email']}")
        print(f"    Password:  {cred['password']}")
        print(f"    Role:      SUPER_ADMIN")
        print(f"    Tenant ID: None (Global Access across all tenants)")
        print("-" * 65)
    print("  Login at: http://localhost:8088/index.html (Check 'Sign in as Staff')")
    print("  Direct:   http://localhost:8088/staff.html")
    print("=" * 65 + "\n")


def main():
    engine = init_db_engine()
    migrate_users_table_nullable_tenant(engine)
    session = get_session()
    try:
        seed_tenantless_superadmin(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
