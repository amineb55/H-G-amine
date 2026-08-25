"""Application settings, loaded from the environment and the .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the HSE inspection analysis service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "HSE Inspection Analysis Service"
    environment: str = "development"
    debug: bool = False

    host: str = "127.0.0.1"
    port: int = 8000

    # Directory where uploaded media is stored (upload logic comes later).
    media_dir: str = "media"

    # Credentials for the analysis engine provider, injected at deploy time.
    analysis_engine_api_key: str = ""
    analysis_engine_model: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
