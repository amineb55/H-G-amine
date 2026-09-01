"""Builders shared by the test modules."""

from datetime import date

from app.models.schemas import (
    EnrichedFinding,
    EnrichedInspectionResult,
    Severity,
    Status,
    ValidationStatus,
)


def make_finding(**overrides) -> EnrichedFinding:
    """An approved, assignable finding; override any field per test."""
    base = dict(
        timestamp_sec=0,
        rule_id="BTP-01",
        observation="A situation that breaches the rule.",
        default_severity=Severity.MAJEUR,
        observed_severity=Severity.MAJEUR,
        severity_reason="The control is required and absent.",
        iso_45001_clause="8.1",
        confidence=0.9,
        status=Status.NC,
        deadline_date=date.today(),
        validation_status=ValidationStatus.APPROVED,
        notify_emails=["owner@example.test"],
    )
    base.update(overrides)
    return EnrichedFinding(**base)


def make_result(findings, inspection_id: str = "test-inspection") -> EnrichedInspectionResult:
    return EnrichedInspectionResult(
        inspection_id=inspection_id,
        referentiel="btp",
        scene_valid=True,
        scene_detected="An active work area.",
        findings=findings,
    )
