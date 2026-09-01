"""Vocabulary and vendor-neutrality guards (principle P9, spec §4.2.8, §7.7).

Vendor names may appear ONLY in the single implementation file of the
dependency they belong to. The allowlist below is the exhaustive map of that
tolerance; adding a file or a token to it is a design decision, not a fix.

Known accepted usages, listed here so the report stays honest:
- ``app/config.py`` carries provider-specific environment-variable aliases
  (a deliberate deployment convenience) and the backend selector defaults
  ("firestore", "gcs").
- ``app/main.py`` names those selector values in two operator-facing log
  hints ("Set STORE_BACKEND=firestore"). Candidate for tightening when the
  configuration surface is reworked.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VENDOR_TOKENS = (
    "gemini",
    "genai",
    "google",
    "brevo",
    "sendinblue",
    "firestore",
    "vertex",
    "gcs",
    "gcloud",
    "openai",
    "anthropic",
)

# The one implementation file of each dependency, and the exact tokens it may use.
ALLOWED_TOKENS: dict[str, set[str]] = {
    "app/services/providers/media_provider.py": {"gemini", "genai", "google"},
    "app/services/notifiers/email_notifier.py": {"brevo"},
    "app/services/inspection_store.py": {"google", "firestore"},
    "app/services/storage.py": {"google", "gcs"},
    "app/config.py": {"brevo", "google", "firestore", "gcs"},
    "app/main.py": {"firestore", "gcs"},
}

# Claiming conformity is banned everywhere: the product only ever says
# coverage, gap, self-assessment (spec §4.2.8; marketing brief §4).
FORBIDDEN_CLAIMS = ("conforme", "conformité", "compliant", "certifié par")


def _scannable_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("app/**/*.py", "app/**/*.txt", "app/**/*.yaml", "templates/*.html"):
        files.extend(PROJECT_ROOT.glob(pattern))
    assert files, "the scan found nothing — the layout moved and the test must follow"
    return sorted(files)


def test_vendor_names_stay_inside_their_implementation_file():
    violations: list[str] = []
    for path in _scannable_files():
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        content = path.read_text(encoding="utf-8").lower()
        found = {token for token in VENDOR_TOKENS if token in content}
        excess = found - ALLOWED_TOKENS.get(relative, set())
        if excess:
            violations.append(f"{relative}: {sorted(excess)}")
    assert not violations, "vendor names outside their implementation file:\n" + "\n".join(
        violations
    )


def test_openapi_schema_is_vendor_neutral(client):
    # Field descriptions ship to API consumers and, via response schemas, to
    # the analysis model itself: no vendor name may appear in any of them.
    schema = json.dumps(client.get("/openapi.json").json()).lower()
    leaked = [token for token in VENDOR_TOKENS if token in schema]
    assert not leaked, f"vendor names in the OpenAPI schema: {leaked}"


def test_no_conformity_claim_anywhere():
    violations: list[str] = []
    for path in _scannable_files():
        content = path.read_text(encoding="utf-8").lower()
        found = [claim for claim in FORBIDDEN_CLAIMS if claim in content]
        if found:
            violations.append(f"{path.relative_to(PROJECT_ROOT)}: {found}")
    assert not violations, "conformity claims found:\n" + "\n".join(violations)


def test_vendor_sdks_are_imported_only_by_their_implementation_file():
    importers: dict[str, list[str]] = {"google": [], "genai": []}
    for path in sorted(PROJECT_ROOT.glob("app/**/*.py")):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import google", "from google")):
                importers["google"].append(relative)
            if "genai" in stripped and stripped.startswith(("import", "from")):
                importers["genai"].append(relative)

    assert set(importers["google"]) <= {
        "app/services/providers/media_provider.py",
        "app/services/inspection_store.py",
        "app/services/storage.py",
    }, f"unexpected vendor SDK importers: {importers['google']}"
    assert set(importers["genai"]) <= {"app/services/providers/media_provider.py"}


def test_provider_modules_are_reached_only_through_their_interface():
    """Structural isolation: callers go through the neutral interfaces."""
    provider_importers: list[str] = []
    notifier_importers: list[str] = []
    for path in sorted(PROJECT_ROOT.glob("app/**/*.py")):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        content = path.read_text(encoding="utf-8")
        if "providers" in content and "import" in content and relative != "app/services/providers/media_provider.py":
            if "from app.services.providers" in content or "import media_provider" in content:
                provider_importers.append(relative)
        if "from app.services.notifiers" in content and relative != "app/services/notifiers/email_notifier.py":
            notifier_importers.append(relative)

    assert provider_importers == ["app/services/analysis_engine.py"]
    assert notifier_importers == ["app/services/notification.py"]
