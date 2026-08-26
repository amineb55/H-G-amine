"""Pydantic models for the HSE inspection finding schema."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels used by the HSE referentials."""

    ARRET_IMMEDIAT = "arret_immediat"
    CRITIQUE = "critique"
    MAJEUR = "majeur"
    MINEUR = "mineur"


class Status(str, Enum):
    """Review status of a finding."""

    NC = "nc"
    A_VERIFIER = "a_verifier"


class Referentiel(str, Enum):
    """Referentials that can be applied to an inspection."""

    BUREAUX = "bureaux"
    BTP = "btp"


class ValidationStatus(str, Enum):
    """Where a finding stands in human validation."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DispatchStatus(str, Enum):
    """Where a finding stands in notification."""

    NOT_QUEUED = "not_queued"
    SENT = "sent"
    FAILED = "failed"


class InspectionStatus(str, Enum):
    """Lifecycle of an inspection request."""

    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Finding(BaseModel):
    """A single non-conformity observed during an inspection."""

    timestamp_sec: int = Field(..., ge=0, description="Offset in the media, in seconds.")
    rule_id: str = Field(..., description="Identifier of the referential rule.")
    observation: str = Field(..., description="What was observed.")
    default_severity: Severity = Field(..., description="Severity defined by the rule.")
    observed_severity: Severity = Field(..., description="Severity retained for this observation.")
    severity_reason: str = Field(..., description="Why the observed severity differs or is confirmed.")
    iso_45001_clause: str = Field(..., description="Related ISO 45001 clause.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1.")
    status: Status = Field(..., description="Review status of the finding.")


class InspectionResult(BaseModel):
    """Result of an inspection analysis."""

    inspection_id: str = Field(..., description="Identifier of the inspection.")
    referentiel: str = Field(..., description="Referential applied to the analysis.")
    scene_valid: bool = Field(..., description="Whether the scene is exploitable.")
    scene_detected: str = Field(..., description="Type of scene detected in the media.")
    findings: list[Finding] = Field(default_factory=list, description="Findings raised by the analysis.")


class InspectionAccepted(BaseModel):
    """Acknowledgement returned when an inspection is queued."""

    inspection_id: str = Field(..., description="Identifier of the inspection.")
    status: InspectionStatus = Field(..., description="Lifecycle status of the inspection.")


class InspectionState(BaseModel):
    """Current state of an inspection."""

    status: InspectionStatus = Field(..., description="Lifecycle status of the inspection.")
    result: "EnrichedInspectionResult | None" = Field(
        None, description="Analysis result, once the inspection is done."
    )
    error: str | None = Field(None, description="Failure reason, when the analysis failed.")


class EnrichedFinding(Finding):
    """A finding with its assignment, deadline and validation state."""

    rule_title: str | None = Field(None, description="What the breached rule requires.")
    assigned_role: str | None = Field(None, description="Role accountable for the finding.")
    assigned_email: str | None = Field(None, description="Address of the accountable role.")
    assigned_name: str | None = Field(None, description="Label of the accountable role.")
    deadline_date: date = Field(..., description="Date the correction is due.")
    immediate: bool = Field(False, description="Whether the work must stop now.")
    notify_emails: list[str] = Field(
        default_factory=list, description="Everyone to notify for this finding."
    )
    requires_review: bool = Field(
        False, description="Whether a human must confirm the finding before it is sent."
    )
    validation_status: ValidationStatus = Field(
        ValidationStatus.PENDING, description="Where the finding stands in human validation."
    )
    dispatch_status: DispatchStatus = Field(
        DispatchStatus.NOT_QUEUED, description="Where the finding stands in notification."
    )
    message_id: str | None = Field(
        None, description="Identifier of the email that carried this finding."
    )
    dispatch_error: str | None = Field(
        None, description="Why the notification failed, when it did."
    )


class EnrichedInspectionResult(BaseModel):
    """An inspection result whose findings carry assignment and validation state."""

    inspection_id: str = Field(..., description="Identifier of the inspection.")
    referentiel: str = Field(..., description="Referential applied to the analysis.")
    scene_valid: bool = Field(..., description="Whether the scene is exploitable.")
    scene_detected: str = Field(..., description="Type of scene detected in the media.")
    findings: list[EnrichedFinding] = Field(
        default_factory=list, description="Findings raised by the analysis."
    )


class ReviewSummary(BaseModel):
    """Counts shown at the top of the review screen."""

    total: int = Field(0, description="Total number of findings.")
    by_severity: dict[str, int] = Field(
        default_factory=dict, description="Findings per observed severity."
    )
    requires_review: int = Field(0, description="Findings a human must confirm.")
    approved: int = Field(0, description="Findings approved so far.")
    rejected: int = Field(0, description="Findings rejected so far.")
    pending: int = Field(0, description="Findings not yet reviewed.")
    has_immediate_stop: bool = Field(
        False, description="Whether at least one finding requires stopping work."
    )


class ReviewResponse(BaseModel):
    """Everything the review screen needs for one inspection."""

    inspection_id: str = Field(..., description="Identifier of the inspection.")
    status: InspectionStatus = Field(..., description="Lifecycle status of the inspection.")
    result: EnrichedInspectionResult | None = Field(
        None, description="Enriched result, once the inspection is done."
    )
    summary: ReviewSummary = Field(
        default_factory=ReviewSummary, description="Counts across the findings."
    )
    error: str | None = Field(None, description="Failure reason, when the analysis failed.")


class EmailKind(str, Enum):
    """Which of the two emails a recipient can be sent."""

    IMMEDIATE = "immediate"
    DIGEST = "digest"


class EmailOutcome(BaseModel):
    """What happened to one email."""

    email: str = Field(..., description="Address the email was addressed to.")
    kind: EmailKind = Field(..., description="Immediate-stop alert, or the digest.")
    subject: str = Field(..., description="Subject line used.")
    status: DispatchStatus = Field(..., description="Whether the email went out.")
    finding_indexes: list[int] = Field(
        default_factory=list, description="Findings carried by this email."
    )
    message_id: str | None = Field(None, description="Identifier returned by the email service.")
    error: str | None = Field(None, description="Why the email failed, when it did.")


class DispatchResponse(BaseModel):
    """Outcome of notifying the approved findings."""

    inspection_id: str = Field(..., description="Identifier of the inspection.")
    sent: bool = Field(False, description="Whether at least one email went out.")
    emails: list[EmailOutcome] = Field(
        default_factory=list, description="One entry per email attempted."
    )
    sent_count: int = Field(0, description="Emails that went out.")
    failed_count: int = Field(0, description="Emails that failed.")
    already_sent: list[int] = Field(
        default_factory=list, description="Findings skipped because they were already sent."
    )
    approved_from_review: list[int] = Field(
        default_factory=list,
        description="Notified findings that were flagged for review and approved anyway.",
    )
    unassigned: list[int] = Field(
        default_factory=list,
        description="Approved findings with no recipient, so nothing could be sent.",
    )


# InspectionState is declared before EnrichedInspectionResult exists, so its
# forward reference is resolved once the module is fully loaded.
InspectionState.model_rebuild()
