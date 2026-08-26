from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicitly load dotenv if present
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application Configuration Defaults
    env: str = "development"
    debug: bool = False
    app_name: str = "BeNeat Cleaner Finder"

    # BeNeat API
    beneat_api_base: str = "https://lumen.beneat.co"

    # Caching: reference data (provinces/districts/services) is refreshed
    # every N days. Service areas rarely change, so a 30-day TTL is fine.
    cache_ttl_days: int = 30
    cache_dir: Path = Path.home() / ".cache" / "beneat"

    # Listing pagination
    listing_limit: int = 200


# Singleton instance for the application config
settings = Settings()
