import os
import urllib.parse
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Shipment Tracking Agentic Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PORT: int = 8000

    # MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "Nilesh@2026!Secure#MySQL"
    MYSQL_DATABASE: str = "shipment_tracking"

    DATABASE_URL: Optional[str] = None
    FALLBACK_SQLITE_URL: str = "sqlite:///./shipment_tracking.db"
    AUTO_FALLBACK_SQLITE: bool = True

    # Security & Multi-Tenancy Settings
    JWT_SECRET_KEY: str = "cargotrk_super_secret_jwt_key_2026_enterprise_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    API_KEY_LIVE_PREFIX: str = "cargotrk_live_"
    API_KEY_TEST_PREFIX: str = "cargotrk_test_"

    ALLOW_ANONYMOUS_TRACKING: bool = False  # Strictly require authenticated API Key or User session
    DEFAULT_TENANT_SLUG: str = "default-org"
    DEFAULT_TENANT_NAME: str = "Default Enterprise Logistics"

    # Swagger & OpenAPI Documentation Authentication
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME", "nilesh")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD", "nilesh@2026")

    @property
    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # Safely quote special characters in password
        encoded_password = urllib.parse.quote_plus(self.MYSQL_PASSWORD)
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{encoded_password}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
