"""Test foundation.

The environment is pinned to the in-memory store and local storage BEFORE any
application module is imported, so the suite runs anywhere, needs no
credentials, and touches nothing outside a temporary directory. The analysis
engine and the email notifier are replaced at their neutral interfaces: no
test ever reaches a real AI provider or a real email service.
"""

import asyncio
import io
import os
import tempfile

_BASE = tempfile.mkdtemp(prefix="hse-suite-")

_ENV = {
    "STORE_BACKEND": "memory",
    "STORAGE_BACKEND": "local",
    "UPLOAD_DIR": os.path.join(_BASE, "uploads"),
    "EVIDENCE_DIR": os.path.join(_BASE, "evidence"),
    # Fake secrets: present so nothing warns about missing configuration, and
    # known so the redaction tests can assert they never leak.
    "ANALYSIS_ENGINE_API_KEY": "test-engine-secret-0123456789",
    "NOTIFIER_API_KEY": "test-notifier-secret-abcdef",
    "NOTIFIER_SENDER_EMAIL": "sender@example.test",
    "LOG_LEVEL": "WARNING",
}
for _name, _value in _ENV.items():
    os.environ[_name] = _value

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import analysis_engine, inspection_store, notification
from app.services.notifiers.email_notifier import NotificationError


class EngineStub:
    """Configurable stand-in for the analysis engine interface."""

    def __init__(self) -> None:
        self.detection = {
            "referentiel": "btp",
            "confidence": 0.92,
            "justification": "Scaffolding and formwork visible.",
        }
        self.fail_analysis: Exception | None = None
        self.fail_detection: Exception | None = None
        self.analyze_calls: list[tuple[str, str]] = []
        self.detect_calls: list[str] = []

    def result_for(self, referentiel: str) -> dict:
        """A three-finding result covering the severity and review paths."""
        prefix = {"btp": "BTP", "bureaux": "BUR"}.get(referentiel, "BTP")
        return {
            "scene_valid": True,
            "scene_detected": "An active work area.",
            "findings": [
                {
                    "timestamp_sec": 0,
                    "rule_id": f"{prefix}-01",
                    "observation": (
                        "A person works at height with no collective protection "
                        "and no fall arrest."
                    ),
                    "default_severity": "critique",
                    "observed_severity": "arret_immediat",
                    "severity_reason": "Life-threatening exposure at the moment of observation.",
                    "iso_45001_clause": "8.1.2",
                    "confidence": 0.95,
                    "status": "nc",
                },
                {
                    "timestamp_sec": 0,
                    "rule_id": f"{prefix}-03",
                    "observation": "A required control measure is not visible.",
                    "default_severity": "majeur",
                    "observed_severity": "majeur",
                    "severity_reason": "The measure is required and appears absent.",
                    "iso_45001_clause": "8.1",
                    "confidence": 0.55,
                    "status": "a_verifier",
                },
                {
                    "timestamp_sec": 0,
                    "rule_id": f"{prefix}-05",
                    "observation": "Housekeeping is degraded in one area.",
                    "default_severity": "mineur",
                    "observed_severity": "mineur",
                    "severity_reason": "Limited consequences at the time of observation.",
                    "iso_45001_clause": "6.1",
                    "confidence": 0.8,
                    "status": "nc",
                },
            ],
        }


class Outbox:
    """Records every email the application tries to send."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail_for: set[str] = set()

    async def send(self, to, subject, html, attachments=None, cc=None):
        if to in self.fail_for:
            raise NotificationError(f"The email service refused the message to {to}.")
        self.sent.append(
            {
                "to": to,
                "subject": subject,
                "html": html,
                "attachments": list(attachments or []),
                "cc": list(cc or []),
            }
        )
        return f"message-{len(self.sent)}"


@pytest.fixture()
def engine(monkeypatch) -> EngineStub:
    stub = EngineStub()

    async def analyze(media_path: str, referentiel: str) -> dict:
        stub.analyze_calls.append((media_path, referentiel))
        if stub.fail_analysis is not None:
            raise stub.fail_analysis
        return stub.result_for(referentiel)

    async def detect_sector(media_path: str) -> dict:
        stub.detect_calls.append(media_path)
        if stub.fail_detection is not None:
            raise stub.fail_detection
        return dict(stub.detection)

    monkeypatch.setattr(analysis_engine, "analyze", analyze)
    monkeypatch.setattr(analysis_engine, "detect_sector", detect_sector)
    return stub


@pytest.fixture()
def outbox(monkeypatch) -> Outbox:
    box = Outbox()
    monkeypatch.setattr(notification, "send_email", box.send)
    return box


@pytest.fixture()
def client(engine, outbox):
    """The application under test, with both external interfaces stubbed."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _isolated_store():
    """Every test starts and ends with an empty inspection store."""
    asyncio.run(inspection_store.clear())
    yield
    asyncio.run(inspection_store.clear())


@pytest.fixture(scope="session")
def jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (48, 48), (180, 60, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture()
def upload(client, jpeg_bytes):
    """POST inspection media; returns the HTTP response."""

    def _upload(referentiel: str | None = "btp", count: int = 1, media_type: str = "image/jpeg"):
        suffix = media_type.split("/")[-1]
        files = [
            ("files", (f"photo-{index}.{suffix}", jpeg_bytes, media_type))
            for index in range(count)
        ]
        data = {"referentiel": referentiel} if referentiel else {}
        return client.post("/inspections", files=files, data=data)

    return _upload
