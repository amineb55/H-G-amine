"""Concrete email notifier.

This is the ONLY module allowed to know which email provider is in use: its
endpoint, its payload shape and its status codes all stop here. Callers see
``send()`` and, on failure, a readable ``NotificationError``.
"""

import logging
from base64 import b64encode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Transactional email endpoint. Overridable through NOTIFIER_API_URL, which is
# what lets a test point the notifier at a local stub.
DEFAULT_API_URL = "https://api.brevo.com/v3/smtp/email"


class NotificationError(Exception):
    """An email failure, already phrased for the person reading it."""


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
    url = settings.notifier_api_url or DEFAULT_API_URL

    try:
        async with httpx.AsyncClient(timeout=settings.notifier_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise NotificationError("The email service did not respond in time.") from exc
    except httpx.HTTPError as exc:
        raise NotificationError("The email service could not be reached.") from exc

    if response.status_code >= 400:
        body = response.text[:200]
        logger.warning("Email refused for %s: %s %s", to, response.status_code, body)
        raise _readable_error(response.status_code, body)

    try:
        message_id = response.json().get("messageId")
    except ValueError as exc:
        raise NotificationError("The email service returned an unreadable response.") from exc

    if not message_id:
        raise NotificationError("The email service accepted the message without an identifier.")

    logger.info("Email sent to %s (message %s)", to, message_id)
    return str(message_id)
