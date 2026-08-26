"""Application settings, loaded from the environment and the .env file."""

from functools import lru_cache

from pydantic import AliasChoices, Field
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

    log_level: str = "INFO"

    host: str = "127.0.0.1"
    port: int = 8000

    # Uploaded media is stored here until its analysis completes.
    upload_dir: str = "data/uploads"

    # Where inspections are stored: "firestore" (default) or "memory".
    store_backend: str = "firestore"
    store_collection: str = "inspections"
    # Per-operation deadline, and the shorter one used by the startup probe.
    store_timeout_seconds: float = 15.0
    store_probe_seconds: float = 5.0
    # Empty falls back to the project the ambient credentials name.
    store_project_id: str = Field("", validation_alias="GOOGLE_CLOUD_PROJECT")

    # Where evidence images live: "gcs" (default) or "local" for development.
    storage_backend: str = "gcs"
    evidence_bucket: str = Field("", validation_alias="EVIDENCE_BUCKET")
    # Used by the local backend only.
    evidence_dir: str = "data/evidence"
    # Longest edge of a stored evidence image, in pixels.
    evidence_max_pixels: int = 1280

    # Upload limits.
    max_upload_bytes: int = 200 * 1024 * 1024
    max_images: int = 10

    # Analysis engine provider. The model identifier is left empty here so the
    # provider's own default applies; set ANALYSIS_ENGINE_MODEL to override it.
    analysis_engine_api_key: str = ""
    analysis_engine_model: str = ""
    analysis_engine_timeout_seconds: int = 120

    # Frames sampled per second of video. Lower means cheaper.
    analysis_engine_video_fps: float = 1.0

    # Email notifications. The Python names stay provider-neutral; only the
    # environment variable names below are provider-specific.
    notifier_api_key: str = Field(
        "", validation_alias=AliasChoices("NOTIFIER_API_KEY", "BREVO_API_KEY")
    )
    notifier_sender_email: str = Field(
        "", validation_alias=AliasChoices("NOTIFIER_SENDER_EMAIL", "BREVO_SENDER_EMAIL")
    )
    notifier_sender_name: str = "Inspection HSE"
    notifier_timeout_seconds: int = 30
    # Leave empty to use the notifier's own endpoint.
    notifier_api_url: str = ""


    def missing_secrets(self) -> list[str]:
        """Names of the secrets that must be provided but are not set.

        Only names are ever returned — a value is never read back out for
        logging or display.
        """
        required = {
            "ANALYSIS_ENGINE_API_KEY": self.analysis_engine_api_key,
            "NOTIFIER_API_KEY": self.notifier_api_key,
            "NOTIFIER_SENDER_EMAIL": self.notifier_sender_email,
        }
        return sorted(name for name, value in required.items() if not value.strip())


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
