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
