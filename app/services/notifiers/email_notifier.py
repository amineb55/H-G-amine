"""Concrete email notifier.

This is the ONLY module allowed to know which email provider is in use: its
endpoint, its payload shape and its status codes all stop here. Callers see
``send()`` and, on failure, a readable ``NotificationError``.
"""

import asyncio
import logging
import os
import socket
import ssl
from base64 import b64encode
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Transactional email endpoint. Overridable through NOTIFIER_API_URL, which is
# what lets a test point the notifier at a local stub.
DEFAULT_API_URL = "https://api.brevo.com/v3/smtp/email"


class NotificationError(Exception):
    """An email failure, already phrased for the person reading it."""


def _endpoint() -> str:
    """The endpoint in use."""
    return get_settings().notifier_api_url or DEFAULT_API_URL


def _host_of(url: str) -> str:
    """Host part of a URL, for logs and diagnostics. Never carries a secret."""
    try:
        return httpx.URL(url).host or "unknown"
    except Exception:  # noqa: BLE001 - a malformed URL must not break logging
        return "unknown"


def _root_cause(exc: BaseException) -> BaseException:
    """Walk the exception chain down to what actually failed."""
    seen: set[int] = set()
    current: BaseException = exc
    while True:
        nxt = current.__cause__ or current.__context__
        if nxt is None or id(nxt) in seen:
            return current
        seen.add(id(current))
        current = nxt


def _diagnose(exc: Exception, host: str) -> tuple[str, str]:
    """Classify a transport failure.

    Returns ``(category, message)``. The category is a short slug for logs
    and diagnostics; the message is what a person reads.
    """
    if isinstance(exc, httpx.TimeoutException):
        return "timeout", "The email service did not respond in time."

    cause = _root_cause(exc)

    if isinstance(cause, socket.gaierror):
        return "dns", (
            f"The email service host '{host}' could not be resolved. "
            "Check outbound DNS from this environment."
        )
    if isinstance(cause, ConnectionRefusedError):
        return "connection_refused", (
            f"The email service at '{host}' refused the connection."
        )
    if isinstance(cause, ssl.SSLCertVerificationError):
        return "tls_verification", (
            f"The TLS certificate of '{host}' could not be verified. "
            "Check the trust store available to this environment."
        )
    if isinstance(cause, ssl.SSLError):
        return "tls", f"The TLS handshake with '{host}' failed."
    if isinstance(cause, (ConnectionResetError, BrokenPipeError)):
        return "connection_reset", f"The connection to '{host}' was reset."
    if isinstance(cause, OSError) and getattr(cause, "errno", None) == 101:
        return "network_unreachable", (
            f"No network route to '{host}'. Check outbound access from this "
            "environment."
        )
    if isinstance(exc, httpx.ProxyError):
        return "proxy", f"The proxy refused the connection to '{host}'."
    if isinstance(exc, httpx.ConnectError):
        return "connect", f"The email service at '{host}' could not be reached."
    return "transport", f"The email service at '{host}' could not be reached."


def _readable_error(status_code: int, body: str) -> NotificationError:
    """Translate a provider status code into a message worth showing."""
    if status_code in (401, 403):
        return NotificationError("The email service rejected the configured credentials.")
    if status_code == 429:
        return NotificationError("The email service is rate limited. Retry later.")
    if status_code == 400:
        return NotificationError(f"The email service rejected the message as invalid: {body}")
    if status_code >= 500:
        return NotificationError("The email service is temporarily unavailable. Retry later.")
    return NotificationError(f"The email service refused the message (status {status_code}).")


async def send(
    to: str,
    subject: str,
    html: str,
    attachments: list[tuple[str, bytes]] | None = None,
    cc: list[str] | None = None,
) -> str:
    """Send one HTML email and return the provider's message id.

    Args:
        to: Address of the recipient.
        subject: Subject line.
        html: Body of the message.
        attachments: ``(filename, content)`` pairs to attach.
        cc: Addresses copied on the message.

    Raises:
        NotificationError: With a readable message when the send fails.
    """
    settings = get_settings()
    api_key = settings.notifier_api_key
    sender = settings.notifier_sender_email
    if not api_key:
        raise NotificationError("The email service is not configured: no API key is set.")
    if not sender:
        raise NotificationError("The email service is not configured: no sender address is set.")

    payload: dict = {
        "sender": {"email": sender, "name": settings.notifier_sender_name},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
    }
    # A copy never goes to the recipient's own address twice.
    copies = [address for address in (cc or []) if address != to]
    if copies:
        payload["cc"] = [{"email": address} for address in copies]
    if attachments:
        payload["attachment"] = [
            {"name": name, "content": b64encode(content).decode("ascii")}
            for name, content in attachments
        ]
    headers = {
        "api-key": api_key,
        "accept": "application/json",
        "content-type": "application/json",
    }
    url = _endpoint()

    host = _host_of(url)
    try:
        async with httpx.AsyncClient(timeout=settings.notifier_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
    except Exception as exc:  # noqa: BLE001 - diagnosed, logged, then wrapped
        category, message = _diagnose(exc, host)
        cause = _root_cause(exc)
        # The payload and the headers are never logged: they carry the key.
        logger.error(
            "Email transport failure [%s] host=%s recipient=%s: %s: %s "
            "(root cause %s: %s)",
            category, host, to,
            exc.__class__.__name__, exc,
            cause.__class__.__name__, cause,
            exc_info=True,
        )
        raise NotificationError(message) from exc

    if response.status_code >= 400:
        body = response.text[:200]
        logger.error(
            "Email refused [http_%s] host=%s recipient=%s: %s",
            response.status_code, host, to, body,
        )
        raise _readable_error(response.status_code, body)

    try:
        message_id = response.json().get("messageId")
    except ValueError as exc:
        raise NotificationError("The email service returned an unreadable response.") from exc

    if not message_id:
        raise NotificationError("The email service accepted the message without an identifier.")

    logger.info("Email sent to %s (message %s)", to, message_id)
    return str(message_id)


# --- diagnostics ------------------------------------------------------------
#
# Temporary tooling for investigating why sending fails in one environment and
# not another. Nothing here returns a secret: only whether one is configured,
# the host being contacted, and what each step of the connection did.

# Read-only path used to prove the credentials work without sending mail.
ACCOUNT_PATH = "/v3/account"
DEFAULT_ACCOUNT_URL = "https://api.brevo.com/v3/account"


def _account_url() -> str:
    """The read-only endpoint, on the same host that sending uses.

    When a custom endpoint is configured the probe follows it, so the check
    exercises the host mail would actually go to.
    """
    configured = get_settings().notifier_api_url.strip()
    if not configured:
        return DEFAULT_ACCOUNT_URL
    try:
        return str(httpx.URL(configured).copy_with(path=ACCOUNT_PATH, query=None))
    except Exception:  # noqa: BLE001 - a malformed override falls back
        return DEFAULT_ACCOUNT_URL


def _resolve(host: str, port: int) -> dict[str, Any]:
    """Resolve a host name, reporting what DNS returned."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
    addresses = sorted({info[4][0] for info in infos})
    return {"ok": True, "addresses": addresses}


def _connect(host: str, port: int, timeout: float, use_tls: bool) -> dict[str, Any]:
    """Open a TCP connection, and complete the TLS handshake when applicable.

    TLS is attempted only for an https endpoint: forcing a handshake on a
    plain http endpoint would report a failure that does not exist.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            if not use_tls:
                return {"ok": True, "tls": "not applicable (plain http endpoint)"}
            context = ssl.create_default_context()
            with context.wrap_socket(raw, server_hostname=host) as secured:
                peer = secured.getpeercert() or {}
                issuer = {k: v for entry in peer.get("issuer", ()) for k, v in entry}
                return {
                    "ok": True,
                    "tls_version": secured.version(),
                    "certificate_issuer": issuer.get("organizationName")
                    or issuer.get("commonName"),
                    "certificate_expires": peer.get("notAfter"),
                }
    except Exception as exc:  # noqa: BLE001 - every failure is a result here
        category, message = _diagnose(exc, host)
        cause = _root_cause(exc)
        return {
            "ok": False,
            "category": category,
            "error": f"{cause.__class__.__name__}: {cause}",
            "message": message,
        }


async def _account_probe(timeout: float) -> dict[str, Any]:
    """Call a read-only endpoint to prove the round trip and the credentials.

    Sends no mail. Only the status code is reported — never the response body,
    which describes the account.
    """
    api_key = get_settings().notifier_api_key
    url = _account_url()
    host = _host_of(url)
    if not api_key:
        return {"ok": False, "host": host, "skipped": "no API key configured"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                url, headers={"api-key": api_key, "accept": "application/json"}
            )
    except Exception as exc:  # noqa: BLE001
        category, message = _diagnose(exc, host)
        cause = _root_cause(exc)
        return {
            "ok": False,
            "host": host,
            "category": category,
            "error": f"{cause.__class__.__name__}: {cause}",
            "message": message,
        }

    result: dict[str, Any] = {"ok": response.status_code < 400,
                              "host": host,
                              "status_code": response.status_code}
    if response.status_code in (401, 403):
        result["message"] = (
            f"'{host}' answered {response.status_code}. That is a rejected "
            "credential when it comes from the email service — check whether a "
            "proxy answered instead."
        )
    elif response.status_code >= 400:
        result["message"] = f"The email service answered {response.status_code}."
    return result


async def diagnose_connectivity() -> dict[str, Any]:
    """Check what the notifier can actually reach, step by step.

    Returns a structure describing configuration presence, DNS, TCP/TLS and a
    read-only API call. No secret value is ever included.
    """
    settings = get_settings()
    url = _endpoint()
    host = _host_of(url)
    timeout = float(settings.notifier_timeout_seconds)
    parsed = httpx.URL(url)
    scheme = parsed.scheme or "https"
    use_tls = scheme == "https"
    port = parsed.port or (443 if use_tls else 80)

    report: dict[str, Any] = {
        "endpoint_host": host,
        "endpoint_port": port,
        "endpoint_scheme": scheme,
        "using_default_endpoint": not settings.notifier_api_url,
        "configuration": {
            "api_key_present": bool(settings.notifier_api_key.strip()),
            "sender_address_present": bool(settings.notifier_sender_email.strip()),
            "timeout_seconds": timeout,
        },
        "proxy_environment": sorted(
            name
            for name in (
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                "http_proxy", "https_proxy", "all_proxy", "no_proxy",
            )
            if os.environ.get(name)
        ),
    }

    report["dns"] = await asyncio.to_thread(_resolve, host, port)
    if report["dns"].get("ok"):
        report["tcp_tls"] = await asyncio.to_thread(_connect, host, port, timeout, use_tls)
    else:
        report["tcp_tls"] = {"ok": False, "skipped": "DNS did not resolve"}

    report["api_call"] = await _account_probe(timeout)

    failed = next(
        (
            step
            for step in ("dns", "tcp_tls", "api_call")
            if not report[step].get("ok")
        ),
        None,
    )
    report["outcome"] = "ok" if failed is None else f"failed at {failed}"
    return report
