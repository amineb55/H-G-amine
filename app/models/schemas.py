"""Pydantic models for the HSE inspection finding schema."""

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
    result: InspectionResult | None = Field(
        None, description="Analysis result, once the inspection is done."
    )
    error: str | None = Field(None, description="Failure reason, when the analysis failed.")
