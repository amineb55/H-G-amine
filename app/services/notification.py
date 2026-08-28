"""Turning approved findings into the emails their recipients receive.

Emails are grouped by recipient rather than by finding: one person gets one
message listing everything they own. Findings that require work to stop
immediately are pulled out into their own message, sent first, so an imminent
danger is never buried inside a digest.

This module holds no provider-specific code; it calls the notifier interface.
"""

import asyncio
import logging
from base64 import b64encode
from datetime import date
from html import escape
from pathlib import Path

from app.models.schemas import (
    DispatchStatus,
    FindingSource,
    EmailKind,
    EmailOutcome,
    EnrichedFinding,
    EnrichedInspectionResult,
    Severity,
    ValidationStatus,
)
from app.services import inspection_prompt, report, storage
from app.services.notifiers.email_notifier import NotificationError
from app.services.notifiers.email_notifier import send as send_email

logger = logging.getLogger(__name__)

IMMEDIATE_SUBJECT_PREFIX = "[IMMEDIATE STOP]"

# Evidence larger than this is left to the attached report rather than inlined.
MAX_INLINE_IMAGE_BYTES = 2 * 1024 * 1024

SEVERITY_LABEL: dict[str, str] = {
    Severity.ARRET_IMMEDIAT.value: "Immediate stop",
    Severity.CRITIQUE.value: "Critical",
    Severity.MAJEUR.value: "Major",
    Severity.MINEUR.value: "Minor",
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
    noun = "finding" if count == 1 else "findings"
    if kind is EmailKind.IMMEDIATE:
        return (
            f"{IMMEDIATE_SUBJECT_PREFIX} Inspection {result.inspection_id} — "
            f"{count} {noun} requiring immediate action"
        )
    return f"Inspection {result.inspection_id} — {count} {noun} to address"


def _inline_image(inspection_id: str, finding: EnrichedFinding) -> str:
    """The finding's evidence image, embedded in the body itself."""
    if not finding.evidence_image:
        return ""
    try:
        data = storage.get_evidence(inspection_id, finding.evidence_image)
        if not data or len(data) > MAX_INLINE_IMAGE_BYTES:
            return ""
        encoded = b64encode(data).decode("ascii")
    except Exception:  # noqa: BLE001 - a missing image must not stop the email
        logger.warning("Could not inline evidence %s", finding.evidence_image, exc_info=True)
        return ""
    return (
        f'<img src="data:image/jpeg;base64,{encoded}" alt="Evidence image" '
        f'style="width:100%;max-width:520px;border-radius:6px;'
        f'border:1px solid #dfe3e8;margin-bottom:10px" />'
    )


def _deadline_phrase(findings: list[EnrichedFinding]) -> str:
    """When the soonest correction is due, said plainly."""
    soonest = min(finding.deadline_date for finding in findings)
    today = date.today()
    delta = (soonest - today).days
    stamp = soonest.strftime("%d/%m/%Y")
    if delta <= 0:
        return f"today ({stamp})"
    if delta == 1:
        return f"by tomorrow ({stamp})"
    return f"within {delta} days (by {stamp})"


def _opening(kind: EmailKind, findings: list[EnrichedFinding]) -> str:
    """The first two lines: what this person must do, and by when.

    The greeting above already names their role; this states the action and
    the deadline in prose, rather than leaving them to a table further down.
    """
    count = len(findings)
    noun = "finding" if count == 1 else "findings"

    if kind is EmailKind.IMMEDIATE:
        return (
            f"You must <b>stop the affected work immediately</b> for "
            f"{'this finding' if count == 1 else f'these {count} findings'}. "
            "No grace period applies: action is expected on receipt of this "
            "message.<br/>Work may only resume once the situation has been "
            "corrected and verified."
        )
    return (
        f"{count} {noun} {'has' if count == 1 else 'have'} been assigned to you "
        f"following this inspection. Correction is expected "
        f"<b>{_deadline_phrase(findings)}</b>."
        "<br/>None of these findings requires work to stop."
    )


def _finding_block(inspection_id: str, finding: EnrichedFinding) -> str:
    """Render one finding. Every dynamic value is escaped."""
    severity = finding.observed_severity.value
    colour = SEVERITY_COLOR.get(severity, "#5c6470")
    label = SEVERITY_LABEL.get(severity, severity)

    rows = [
        ("Due", escape(str(finding.deadline_date)) + (" — immediate" if finding.immediate else "")),
        ("Rule", escape(finding.rule_id) + (f" — {escape(finding.rule_title)}" if finding.rule_title else "")),
        ("ISO 45001 clause", escape(finding.iso_45001_clause)),
        ("Timestamp", f"t+{finding.timestamp_sec}s"),
        ("Confidence", f"{round(finding.confidence * 100)}%"),
    ]
    if finding.requires_review:
        rows.append(("Caution", "Low confidence — approved by a validator after review"))
    if finding.source is FindingSource.HUMAN:
        rows.append(("Origin", "Finding added by the auditor"))
    elif finding.edited_by_human:
        rows.append(("Origin", "Detected by the analysis, corrected by the auditor"))

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
        f"{_inline_image(inspection_id, finding)}"
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
    greeting = f"Hello {escape(recipient_name)}," if recipient_name else "Hello,"
    count = len(findings)
    noun = "finding" if count == 1 else "findings"

    opening = _opening(kind, findings)

    if kind is EmailKind.IMMEDIATE:
        banner = (
            '<div style="background:#b3261e;color:#ffffff;padding:14px 16px;'
            'border-radius:6px;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.04em;margin-bottom:16px">'
            "Work must stop immediately"
            '<div style="font-weight:400;text-transform:none;letter-spacing:0;'
            'font-size:13px;margin-top:4px">'
            f"{count} {noun} require{'s' if count == 1 else ''} "
            "the affected work to stop immediately.</div></div>"
        )
    else:
        banner = ""

    blocks = "".join(_finding_block(result.inspection_id, finding) for finding in findings)

    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;background:#f5f6f8;padding:24px;'
        'color:#1a1d21">'
        '<div style="max-width:640px;margin:0 auto">'
        f'<h1 style="font-size:19px;margin:0 0 4px">HSE inspection — '
        f"{escape(inspection_prompt.referentiel_label(result.referentiel))}</h1>"
        f'<div style="font-size:13px;color:#5c6470;margin-bottom:16px">'
        f"Inspection {escape(result.inspection_id)} · {escape(result.scene_detected)}</div>"
        f"{banner}"
        f'<p style="font-size:15px;margin:0 0 8px">{greeting}</p>'
        f'<p style="font-size:15px;margin:0 0 18px;line-height:1.5">{opening}</p>'
        f"{blocks}"
        '<p style="font-size:12px;color:#868e9a;border-top:1px solid #dfe3e8;'
        'padding-top:12px;margin-top:20px">'
        "AI-assisted analysis, validated by an auditor before sending. "
        "The full report is attached to this message as a PDF. "
        "Reply to this message to report an error.</p>"
        "</div></div>"
    )


def _build_report(result: EnrichedInspectionResult) -> list[tuple[str, bytes]]:
    """The PDF report, attached to every email of the dispatch."""
    try:
        return [(report.report_filename(result), report.build_pdf(result))]
    except Exception:  # noqa: BLE001 - a failed report must not stop the emails
        logger.exception("Could not build the report for %s", result.inspection_id)
        return []


async def dispatch(
    result: EnrichedInspectionResult, cc: list[str] | None = None
) -> list[EmailOutcome]:
    """Send one email per recipient and record the outcome on each finding.

    Immediate-stop emails go out first, every message carries the PDF report,
    and any ``cc`` addresses are copied on all of them. A failure is recorded
    against that email's findings only: it never rolls back a send that
    already succeeded.
    """
    groups = group_by_recipient(result)
    # Building the report and each body reads evidence from storage and runs
    # reportlab: both are kept off the event loop.
    attachments = await asyncio.to_thread(_build_report, result) if groups else []
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
        html = await asyncio.to_thread(build_html, result, kind, findings, recipient_name)

        try:
            message_id = await send_email(
                address, subject, html, attachments=attachments, cc=cc
            )
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
                    cc=list(cc or []),
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
                    cc=list(cc or []),
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
                cc=list(cc or []),
            )
        )

    return outcomes
