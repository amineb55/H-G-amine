"""Application settings, loaded from the environment and the .env file."""

from functools import lru_cache

from typing import ClassVar

from pydantic import AliasChoices, Field, PrivateAttr, model_validator
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
    # The detection pass only has to recognise the environment, so it samples
    # far fewer frames than the audit.
    detection_video_fps: float = 0.1
    # Below this, the sector is treated as undetermined and nothing is audited.
    detection_min_confidence: float = 0.7
    # Media kept for an undetermined inspection is deleted after this long,
    # so nothing accumulates when the user never comes back to choose.
    undetermined_media_ttl_hours: float = 6.0

    # Email notifications. The Python names stay provider-neutral; only the
    # environment variable names below are provider-specific.
    notifier_api_key: str = Field(
        "", validation_alias=AliasChoices("NOTIFIER_API_KEY", "BREVO_API_KEY")
    )
    notifier_sender_email: str = Field(
        "", validation_alias=AliasChoices("NOTIFIER_SENDER_EMAIL", "BREVO_SENDER_EMAIL")
    )
    notifier_sender_name: str = "HSE Audit Agent"
    notifier_timeout_seconds: int = 30
    # Leave empty to use the notifier's own endpoint.
    notifier_api_url: str = ""


    # Environment variables whose value is a secret. Whitespace around them is
    # stripped: a value injected from a secret store often carries a trailing
    # newline, and a newline in an HTTP header makes the request illegal.
    _SECRET_FIELDS: ClassVar[dict[str, str]] = {
        "ANALYSIS_ENGINE_API_KEY": "analysis_engine_api_key",
        "NOTIFIER_API_KEY": "notifier_api_key",
        "NOTIFIER_SENDER_EMAIL": "notifier_sender_email",
    }
    # Not secret, but a stray newline breaks them just as badly.
    _TRIMMED_FIELDS: ClassVar[tuple[str, ...]] = (
        "store_project_id", "evidence_bucket", "notifier_api_url",
        "analysis_engine_model", "notifier_sender_name",
    )

    _stripped: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def _trim_values(self) -> "Settings":
        stripped: list[str] = []
        for variable, attribute in self._SECRET_FIELDS.items():
            raw = getattr(self, attribute)
            if isinstance(raw, str) and raw != raw.strip():
                setattr(self, attribute, raw.strip())
                stripped.append(variable)
        for attribute in self._TRIMMED_FIELDS:
            raw = getattr(self, attribute, None)
            if isinstance(raw, str) and raw != raw.strip():
                setattr(self, attribute, raw.strip())
        self._stripped = stripped
        return self

    def stripped_secrets(self) -> list[str]:
        """Names of the secrets that carried surrounding whitespace.

        Only names — a value is never returned.
        """
        return list(self._stripped)

    def secret_values(self) -> list[str]:
        """The configured secret values, longest first.

        Used only to scrub them out of text that is about to be logged or
        returned. Never call this to display or transmit a value.
        """
        values = [getattr(self, attribute) for attribute in self._SECRET_FIELDS.values()]
        return sorted(
            (value.strip() for value in values if isinstance(value, str) and len(value.strip()) >= 6),
            key=len,
            reverse=True,
        )

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


REDACTION_PLACEHOLDER = "[REDACTED]"


def redact(text: str) -> str:
    """Replace any configured secret value found in ``text``.

    Library exceptions quote the offending input back at you — an illegal
    header value carries the credential inside the message. Anything derived
    from an exception passes through here before it is logged or returned.
    """
    if not text:
        return text
    try:
        secrets = get_settings().secret_values()
    except Exception:  # noqa: BLE001 - redaction must never raise
        return text
    for value in secrets:
        if value in text:
            text = text.replace(value, REDACTION_PLACEHOLDER)
    return text
