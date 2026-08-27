"""Pydantic models for the HSE inspection finding schema."""

from datetime import date, datetime
from enum import Enum

import re

from pydantic import BaseModel, Field, field_validator


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


class FindingSource(str, Enum):
    """Who put a finding on the record."""

    AI = "ai"
    HUMAN = "human"


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


class InspectionStage(str, Enum):
    """How far the job has got.

    Only transitions the job can actually observe. Reading the media,
    auditing it against the referential and grading the severity all happen
    inside one call to the analysis engine, so they share the ANALYSE stage
    rather than being reported as three separate steps.
    """

    RECEPTION = "reception"
    DETECTION = "detection"
    ANALYSE = "analyse"
    ASSIGNATION = "assignation"
    TERMINE = "termine"


class SectorDetection(BaseModel):
    """What the first pass recognised in the media."""

    referentiel: str | None = Field(
        None, description="Referential detected, when one could be determined."
    )
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="How sure the pass is.")
    justification: str = Field("", description="What was recognised, in French.")
    determined: bool = Field(
        False, description="Whether the sector was determined with enough confidence."
    )


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
    stage: InspectionStage | None = Field(
        None, description="How far the job has got. Only observed transitions."
    )
    detection: SectorDetection | None = Field(
        None, description="Outcome of the sector detection pass, when it ran."
    )
    media_retained: bool = Field(
        False, description="Whether the media is still held, pending a sector choice."
    )
    result: "EnrichedInspectionResult | None" = Field(
        None, description="Analysis result, once the inspection is done."
    )
    error: str | None = Field(None, description="Failure reason, when the analysis failed.")


class EnrichedFinding(Finding):
    """A finding with its assignment, deadline and validation state."""

    rule_title: str | None = Field(None, description="What the breached rule requires.")
    evidence_image: str | None = Field(
        None, description="File name of the retained evidence image."
    )
    source: FindingSource = Field(
        FindingSource.AI, description="Whether the analysis or an auditor raised it."
    )
    edited_by_human: bool = Field(False, description="Whether an auditor corrected it.")
    original_severity: Severity | None = Field(
        None, description="Severity the analysis reported, when an auditor changed it."
    )
    original_observation: str | None = Field(
        None, description="Observation the analysis reported, when an auditor changed it."
    )
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
    captured_at: datetime | None = Field(
        None, description="When the media was shot, read from its metadata. Never inferred."
    )
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
    referentiel_label: str | None = Field(
        None, description="Human name of the referential, for display."
    )
    detection: SectorDetection | None = Field(
        None, description="Outcome of the sector detection pass, when it ran."
    )
    media_retained: bool = Field(
        False, description="Whether the media is still held, pending a sector choice."
    )
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
    cc: list[str] = Field(default_factory=list, description="Addresses copied on the email.")
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


class FindingEdit(BaseModel):
    """An auditor's correction to a finding. Omitted fields are left alone."""

    observed_severity: Severity | None = Field(None, description="Severity the auditor retains.")
    observation: str | None = Field(None, min_length=1, description="Corrected observation.")
    rule_id: str | None = Field(None, min_length=1, description="Rule the auditor attributes it to.")
    assigned_role: str | None = Field(None, min_length=1, description="Role the auditor assigns.")


class ManualFinding(BaseModel):
    """A finding an auditor adds because the analysis missed it."""

    rule_id: str = Field(..., min_length=1, description="Rule that is breached.")
    observation: str = Field(..., min_length=1, description="What the auditor observed.")
    observed_severity: Severity = Field(..., description="Severity the auditor retains.")
    timestamp_sec: int = Field(0, ge=0, description="Where in the media it is visible.")


class DispatchRequest(BaseModel):
    """Options for one dispatch."""

    cc: list[str] = Field(
        default_factory=list,
        description="Extra addresses copied on every email of this dispatch.",
    )

    @field_validator("cc")
    @classmethod
    def _check_addresses(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in values:
            address = raw.strip()
            if not address:
                continue
            if not _EMAIL_PATTERN.match(address):
                raise ValueError(f"'{address}' is not a valid address")
            if address not in cleaned:
                cleaned.append(address)
        return cleaned


class ReferentielChoice(BaseModel):
    """An auditor picking the referential to audit against."""

    referentiel: Referentiel = Field(..., description="Referential to apply.")
