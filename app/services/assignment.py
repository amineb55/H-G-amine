"""Assignment of findings to accountable roles, and deadline computation.

The catalog lives in ``app/rules/responsables.yaml`` so who is accountable for
what can be changed without touching code.
"""

import logging
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.models.schemas import (
    EnrichedFinding,
    EnrichedInspectionResult,
    Finding,
    InspectionResult,
    ReviewSummary,
    Severity,
    Status,
    ValidationStatus,
)
from app.services.inspection_prompt import PromptError, Rule, load_catalog

logger = logging.getLogger(__name__)

RESPONSABLES_PATH = Path(__file__).resolve().parent.parent / "rules" / "responsables.yaml"

# Days allowed to correct a finding, by the severity actually observed.
DEADLINE_DAYS_BY_SEVERITY: dict[Severity, int] = {
    Severity.ARRET_IMMEDIAT: 0,
    Severity.CRITIQUE: 1,
    Severity.MAJEUR: 7,
    Severity.MINEUR: 30,
}

# Order used to sort findings, most serious first.
SEVERITY_ORDER: list[Severity] = [
    Severity.ARRET_IMMEDIAT,
    Severity.CRITIQUE,
    Severity.MAJEUR,
    Severity.MINEUR,
]

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AssignmentError(Exception):
    """Raised when the assignment catalog cannot be loaded."""


class Responsable(BaseModel):
    """A role that can be held accountable for a finding."""

    email: str = Field(..., description="Address notified for this role.")
    name: str = Field(..., description="Label shown for this role.")

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        if not _EMAIL_PATTERN.match(value):
            raise ValueError(f"'{value}' is not a valid address")
        return value


class Escalation(BaseModel):
    """Who is notified beyond the assigned role."""

    arret_immediat_also_notifies: str | None = Field(
        None, description="Role also notified when work must stop immediately."
    )


class ResponsableCatalog(BaseModel):
    """Roles, per-rule assignments and escalation."""

    roles: dict[str, Responsable] = Field(..., min_length=1)
    assignments: dict[str, str] = Field(default_factory=dict)
    escalation: Escalation = Field(default_factory=Escalation)

    @model_validator(mode="after")
    def _check_references(self) -> "ResponsableCatalog":
        for rule_id, role_key in self.assignments.items():
            if role_key not in self.roles:
                raise ValueError(
                    f"rule '{rule_id}' is assigned to unknown role '{role_key}'"
                )
        escalated = self.escalation.arret_immediat_also_notifies
        if escalated is not None and escalated not in self.roles:
            raise ValueError(f"escalation targets unknown role '{escalated}'")
        return self


@lru_cache
def load_responsables() -> ResponsableCatalog:
    """Load and validate the assignment catalog."""
    try:
        raw = yaml.safe_load(RESPONSABLES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssignmentError(f"No assignment catalog at {RESPONSABLES_PATH}.") from exc
    except yaml.YAMLError as exc:
        raise AssignmentError("The assignment catalog is not valid YAML.") from exc

    try:
        return ResponsableCatalog.model_validate(raw)
    except ValidationError as exc:
        raise AssignmentError(
            f"The assignment catalog does not match the expected structure: {exc}"
        ) from exc


def _find_rule(referentiel: str, rule_id: str) -> Rule | None:
    """Return the catalog rule a finding refers to, if it exists."""
    try:
        catalog = load_catalog(referentiel)
    except PromptError:
        logger.warning("No rule catalog for referential '%s'", referentiel)
        return None
    for rule in catalog.rules:
        if rule.id == rule_id:
            return rule
    logger.warning("Rule '%s' is not in catalog '%s'", rule_id, referentiel)
    return None


def _deadline_days(finding: Finding, rule: Rule | None) -> int:
    """Days allowed to correct a finding.

    Driven by the severity actually observed. If that severity is not one the
    grid knows, the rule's own ``deadline_days`` is used instead.
    """
    known = DEADLINE_DAYS_BY_SEVERITY.get(finding.observed_severity)
    if known is not None:
        return known
    if rule is not None:
        logger.info(
            "Unknown severity '%s' on %s; falling back to the rule deadline of %d days",
            finding.observed_severity, finding.rule_id, rule.deadline_days,
        )
        return rule.deadline_days
    logger.warning("No deadline available for '%s'; defaulting to today", finding.rule_id)
    return 0


def enrich_finding(
    finding: Finding, referentiel: str, *, today: date | None = None
) -> EnrichedFinding:
    """Attach the accountable role, the deadline and the validation state."""
    catalog = load_responsables()
    today = today or date.today()

    role_key = catalog.assignments.get(finding.rule_id)
    role = catalog.roles.get(role_key) if role_key else None
    if role is None:
        logger.warning(
            "Rule '%s' has no entry in the assignment catalog; finding left unassigned",
            finding.rule_id,
        )

    rule = _find_rule(referentiel, finding.rule_id)
    immediate = finding.observed_severity == Severity.ARRET_IMMEDIAT
    deadline_date = today + timedelta(days=_deadline_days(finding, rule))

    notify: list[str] = []
    if role is not None:
        notify.append(role.email)
    if immediate:
        escalated_key = catalog.escalation.arret_immediat_also_notifies
        escalated = catalog.roles.get(escalated_key) if escalated_key else None
        if escalated is not None:
            notify.append(escalated.email)

    # Roles can share an address; notify each address once.
    notify_emails = list(dict.fromkeys(notify))

    return EnrichedFinding(
        **finding.model_dump(),
        rule_title=rule.title if rule is not None else None,
        assigned_role=role_key if role is not None else None,
        assigned_email=role.email if role is not None else None,
        assigned_name=role.name if role is not None else None,
        deadline_date=deadline_date,
        immediate=immediate,
        notify_emails=notify_emails,
        requires_review=finding.status == Status.A_VERIFIER,
        validation_status=ValidationStatus.PENDING,
    )


def _severity_rank(finding: EnrichedFinding) -> tuple[int, int]:
    """Sort key placing the most serious findings first."""
    try:
        rank = SEVERITY_ORDER.index(finding.observed_severity)
    except ValueError:
        rank = len(SEVERITY_ORDER)
    return rank, finding.timestamp_sec


def enrich(result: InspectionResult, *, today: date | None = None) -> EnrichedInspectionResult:
    """Enrich every finding of a result and order them by severity."""
    findings = [
        enrich_finding(finding, result.referentiel, today=today) for finding in result.findings
    ]
    findings.sort(key=_severity_rank)
    return EnrichedInspectionResult(
        inspection_id=result.inspection_id,
        referentiel=result.referentiel,
        scene_valid=result.scene_valid,
        scene_detected=result.scene_detected,
        findings=findings,
    )


def summarize(result: EnrichedInspectionResult | None) -> ReviewSummary:
    """Count findings by severity and validation state."""
    if result is None:
        return ReviewSummary()

    by_severity = {severity.value: 0 for severity in SEVERITY_ORDER}
    counts = {status.value: 0 for status in ValidationStatus}
    requires_review = 0

    for finding in result.findings:
        key = finding.observed_severity.value
        by_severity[key] = by_severity.get(key, 0) + 1
        counts[finding.validation_status.value] += 1
        if finding.requires_review:
            requires_review += 1

    return ReviewSummary(
        total=len(result.findings),
        by_severity=by_severity,
        requires_review=requires_review,
        approved=counts[ValidationStatus.APPROVED.value],
        rejected=counts[ValidationStatus.REJECTED.value],
        pending=counts[ValidationStatus.PENDING.value],
        has_immediate_stop=any(f.immediate for f in result.findings),
    )
