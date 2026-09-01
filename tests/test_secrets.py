"""Secrets never reach any output: redaction, whitespace stripping, naming."""

import logging
import sys

from app.config import REDACTION_PLACEHOLDER, Settings, get_settings, redact

ENGINE_SECRET = "test-engine-secret-0123456789"
NOTIFIER_SECRET = "test-notifier-secret-abcdef"


def test_redact_scrubs_every_configured_secret():
    text = f"header {ENGINE_SECRET} and body {NOTIFIER_SECRET}"
    cleaned = redact(text)
    assert ENGINE_SECRET not in cleaned
    assert NOTIFIER_SECRET not in cleaned
    assert cleaned.count(REDACTION_PLACEHOLDER) == 2


def test_redact_leaves_ordinary_text_alone():
    assert redact("nothing secret here") == "nothing secret here"
    assert redact("") == ""


def test_redacting_formatter_scrubs_tracebacks():
    from app.main import RedactingFormatter

    formatter = RedactingFormatter("%(message)s")
    try:
        raise RuntimeError(f"Illegal header value b'{NOTIFIER_SECRET}\\n'")
    except RuntimeError:
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="sending failed", args=(), exc_info=sys.exc_info(),
        )
    output = formatter.format(record)
    assert NOTIFIER_SECRET not in output, "a traceback must never carry a secret"
    assert REDACTION_PLACEHOLDER in output


def test_whitespace_around_secrets_is_stripped_and_named():
    settings = Settings(
        analysis_engine_api_key="  padded-key-123456\n",
        notifier_api_key="clean-key-654321",
        notifier_sender_email="sender@example.test",
    )
    assert settings.analysis_engine_api_key == "padded-key-123456"
    assert settings.stripped_secrets() == ["ANALYSIS_ENGINE_API_KEY"]


def test_missing_secrets_are_reported_by_name_only():
    settings = Settings(
        analysis_engine_api_key="", notifier_api_key="", notifier_sender_email=" "
    )
    assert settings.missing_secrets() == [
        "ANALYSIS_ENGINE_API_KEY",
        "NOTIFIER_API_KEY",
        "NOTIFIER_SENDER_EMAIL",
    ]


def test_secret_values_are_sorted_longest_first_and_skip_short_ones():
    settings = Settings(
        analysis_engine_api_key="short",  # under 6 characters: never scrubbed,
        notifier_api_key="a-much-longer-value-here",  # or it would mangle text
        notifier_sender_email="sender@example.test",
    )
    values = settings.secret_values()
    assert "short" not in values
    assert values == sorted(values, key=len, reverse=True)


def test_error_responses_never_carry_a_secret(client, upload, engine):
    engine.fail_analysis = RuntimeError(
        f"Upstream rejected key '{get_settings().analysis_engine_api_key}'"
    )
    inspection_id = upload().json()["inspection_id"]
    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "failed"
    assert get_settings().analysis_engine_api_key not in state["error"]
    assert REDACTION_PLACEHOLDER in state["error"]
