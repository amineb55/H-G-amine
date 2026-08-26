"""Turning approved findings into the emails their recipients receive.

Emails are grouped by recipient rather than by finding: one person gets one
message listing everything they own. Findings that require work to stop
immediately are pulled out into their own message, sent first, so an imminent
danger is never buried inside a digest.

This module holds no provider-specific code; it calls the notifier interface.
"""

import logging
from html import escape

from app.models.schemas import (
    DispatchStatus,
    EmailKind,
    EmailOutcome,
    EnrichedFinding,
    EnrichedInspectionResult,
    Severity,
    ValidationStatus,
)
from app.services.notifiers.email_notifier import NotificationError
from app.services.notifiers.email_notifier import send as send_email

logger = logging.getLogger(__name__)

IMMEDIATE_SUBJECT_PREFIX = "[ARRET IMMEDIAT]"

SEVERITY_LABEL: dict[str, str] = {
    Severity.ARRET_IMMEDIAT.value: "Arrêt immédiat",
    Severity.CRITIQUE.value: "Critique",
    Severity.MAJEUR.value: "Majeur",
    Severity.MINEUR.value: "Mineur",
}
SEVERITY_COLOR: dict[str, str] = {
    Severity.ARRET_IMMEDIAT.value: "#b3261e",
    Severity.CRITIQUE.value: "#c2410c",
    Severity.MAJEUR.value: "#a16207",
    Severity.MINEUR.value: "#0f6f8f",
}


def is_notifiable(finding: EnrichedFinding) -> bool:
    """Whether a finding should be carried by this dispatch.

    Approval is what queues a finding, low confidence included. Anything
    already sent is left alone, so calling dispatch twice never sends twice.
    """
    return (
        finding.validation_status is ValidationStatus.APPROVED
        and finding.dispatch_status is not DispatchStatus.SENT
        and bool(finding.notify_emails)
    )


def group_by_recipient(
    result: EnrichedInspectionResult,
) -> dict[tuple[str, EmailKind], list[int]]:
    """Map each (recipient, email kind) to the findings it must carry.

    A finding reaches every address in its ``notify_emails``, so an escalation
    recipient sees it too, and each address gets at most two emails.
    """
    groups: dict[tuple[str, EmailKind], list[int]] = {}
    for index, finding in enumerate(result.findings):
        if not is_notifiable(finding):
            continue
        kind = EmailKind.IMMEDIATE if finding.immediate else EmailKind.DIGEST
        for address in finding.notify_emails:
            groups.setdefault((address, kind), []).append(index)
    return groups


def build_subject(result: EnrichedInspectionResult, kind: EmailKind, count: int) -> str:
    """Subject line for one email."""
    noun = "constat" if count == 1 else "constats"
    if kind is EmailKind.IMMEDIATE:
        return (
            f"{IMMEDIATE_SUBJECT_PREFIX} Inspection {result.inspection_id} — "
            f"{count} {noun} à traiter immédiatement"
        )
    return f"Inspection {result.inspection_id} — {count} {noun} à traiter"


def _finding_block(finding: EnrichedFinding) -> str:
    """Render one finding. Every dynamic value is escaped."""
    severity = finding.observed_severity.value
    colour = SEVERITY_COLOR.get(severity, "#5c6470")
    label = SEVERITY_LABEL.get(severity, severity)

    rows = [
        ("Échéance", escape(str(finding.deadline_date)) + (" — immédiat" if finding.immediate else "")),
        ("Règle", escape(finding.rule_id) + (f" — {escape(finding.rule_title)}" if finding.rule_title else "")),
        ("Clause ISO 45001", escape(finding.iso_45001_clause)),
        ("Horodatage", f"t+{finding.timestamp_sec}s"),
        ("Confiance", f"{round(finding.confidence * 100)}%"),
    ]
    if finding.requires_review:
        rows.append(("Vigilance", "Confiance faible — approuvé par un valideur après vérification"))

    detail = "".join(
        f'<tr><td style="padding:3px 12px 3px 0;color:#5c6470;font-size:13px;'
        f'white-space:nowrap;vertical-align:top">{name}</td>'
        f'<td style="padding:3px 0;font-size:13px;color:#1a1d21">{value}</td></tr>'
        for name, value in rows
    )

    return (
        f'<div style="border-left:4px solid {colour};background:#ffffff;'
        f'border:1px solid #dfe3e8;border-left-width:4px;border-radius:6px;'
        f'padding:14px 16px;margin-bottom:12px">'
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.05em;color:{colour};margin-bottom:6px">{escape(label)}</div>'
        f'<div style="font-size:15px;color:#1a1d21;margin-bottom:8px">'
        f"{escape(finding.observation)}</div>"
        f'<div style="font-size:13px;color:#5c6470;border-left:2px solid #dfe3e8;'
        f'padding-left:10px;margin-bottom:10px">{escape(finding.severity_reason)}</div>'
        f'<table cellpadding="0" cellspacing="0" style="border-top:1px solid #dfe3e8;'
        f'padding-top:8px;width:100%">{detail}</table>'
        f"</div>"
    )


def build_html(
    result: EnrichedInspectionResult,
    kind: EmailKind,
    findings: list[EnrichedFinding],
    recipient_name: str | None,
) -> str:
    """Build the body of one recipient's email."""
    greeting = f"Bonjour {escape(recipient_name)}," if recipient_name else "Bonjour,"
    count = len(findings)
    noun = "constat" if count == 1 else "constats"

    if kind is EmailKind.IMMEDIATE:
        banner = (
            '<div style="background:#b3261e;color:#ffffff;padding:14px 16px;'
            'border-radius:6px;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.04em;margin-bottom:16px">'
            "Arrêt immédiat de l'activité"
            '<div style="font-weight:400;text-transform:none;letter-spacing:0;'
            'font-size:13px;margin-top:4px">'
            f"{count} {noun} {'impose' if count == 1 else 'imposent'} "
            "l'arrêt immédiat des travaux concernés.</div></div>"
        )
        lead = (
            f"{count} {noun} {'relève' if count == 1 else 'relèvent'} d'un arrêt "
            "immédiat de l'activité. Une action est attendue sans délai."
        )
    else:
        banner = ""
        lead = (
            f"{count} {noun} vous {'est' if count == 1 else 'sont'} "
            f"{'attribué' if count == 1 else 'attribués'} à la suite de "
            "l'inspection ci-dessous."
        )

    blocks = "".join(_finding_block(finding) for finding in findings)

    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;background:#f5f6f8;padding:24px;'
        'color:#1a1d21">'
        '<div style="max-width:640px;margin:0 auto">'
        f'<h1 style="font-size:19px;margin:0 0 4px">Inspection HSE — '
        f"{escape(result.referentiel)}</h1>"
        f'<div style="font-size:13px;color:#5c6470;margin-bottom:16px">'
        f"Inspection {escape(result.inspection_id)} · {escape(result.scene_detected)}</div>"
        f"{banner}"
        f'<p style="font-size:15px;margin:0 0 4px">{greeting}</p>'
        f'<p style="font-size:15px;margin:0 0 18px;color:#5c6470">{lead}</p>'
        f"{blocks}"
        '<p style="font-size:12px;color:#868e9a;border-top:1px solid #dfe3e8;'
        'padding-top:12px;margin-top:20px">'
        "Analyse assistée par IA, validée par un auditeur avant envoi. "
        "Répondez à ce message pour signaler une erreur.</p>"
        "</div></div>"
    )


async def dispatch(result: EnrichedInspectionResult) -> list[EmailOutcome]:
    """Send one email per recipient and record the outcome on each finding.

    Immediate-stop emails go out first. A failure is recorded against that
    email's findings only: it never rolls back a send that already succeeded.
    """
    groups = group_by_recipient(result)
    # Immediate-stop alerts first, then digests; stable order within each.
    ordered = sorted(groups.items(), key=lambda item: (item[0][1] is not EmailKind.IMMEDIATE, item[0][0]))

    outcomes: list[EmailOutcome] = []
    for (address, kind), indexes in ordered:
        findings = [result.findings[i] for i in indexes]
        recipient_name = next(
            (f.assigned_name for f in findings if f.assigned_email == address and f.assigned_name),
            None,
        )
        subject = build_subject(result, kind, len(findings))
        html = build_html(result, kind, findings, recipient_name)

        try:
            message_id = await send_email(address, subject, html)
        except NotificationError as exc:
            logger.warning("Email to %s failed: %s", address, exc)
            for finding in findings:
                # Never downgrade a finding another email already delivered.
                if finding.dispatch_status is not DispatchStatus.SENT:
                    finding.dispatch_status = DispatchStatus.FAILED
                    finding.dispatch_error = str(exc)
            outcomes.append(
                EmailOutcome(
                    email=address, kind=kind, subject=subject,
                    status=DispatchStatus.FAILED, finding_indexes=indexes, error=str(exc),
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - one bad email must not stop the rest
            logger.exception("Unexpected failure sending to %s", address)
            message = f"The email could not be sent: {exc}"
            for finding in findings:
                if finding.dispatch_status is not DispatchStatus.SENT:
                    finding.dispatch_status = DispatchStatus.FAILED
                    finding.dispatch_error = message
            outcomes.append(
                EmailOutcome(
                    email=address, kind=kind, subject=subject,
                    status=DispatchStatus.FAILED, finding_indexes=indexes, error=message,
                )
            )
            continue

        for finding in findings:
            finding.dispatch_status = DispatchStatus.SENT
            finding.message_id = message_id
            finding.dispatch_error = None
        outcomes.append(
            EmailOutcome(
                email=address, kind=kind, subject=subject,
                status=DispatchStatus.SENT, finding_indexes=indexes, message_id=message_id,
            )
        )

    return outcomes
