"""Rule catalogs and system prompt assembly.

The catalogs live in ``app/rules/`` as one YAML file per referential and the
prompt in ``app/prompts/inspection.txt``, so both can be edited without
touching code. This module holds no provider-specific logic.
"""

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.models.schemas import Referentiel, Severity

logger = logging.getLogger(__name__)

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "inspection.txt"
DETECTION_PATH = Path(__file__).resolve().parent.parent / "prompts" / "detection.txt"

REFERENTIEL_TOKEN = "{{REFERENTIEL}}"
RULES_TOKEN = "{{RULES}}"
SECTORS_TOKEN = "{{SECTORS}}"

# Returned when the media shows a sector the demonstration does not cover.
UNSUPPORTED = "autre"


class PromptError(Exception):
    """Raised when a catalog or the prompt template cannot be loaded."""


class Rule(BaseModel):
    """One auditable rule of a referential."""

    id: str = Field(..., description="Identifier of the rule.")
    title: str = Field(..., description="What the rule requires.")
    default_severity: Severity = Field(..., description="Severity defined by the rule.")
    deadline_days: int = Field(..., ge=0, description="Days allowed to correct a breach.")
    iso_45001_clause: str = Field(..., description="Related ISO 45001 clause.")


class RuleCatalog(BaseModel):
    """The set of rules applied to one referential."""

    referentiel: Referentiel = Field(..., description="Referential these rules belong to.")
    label: str = Field(..., min_length=1, description="Human name shown to readers.")
    description: str = Field("", description="One line describing what the referential covers.")
    rules: list[Rule] = Field(..., min_length=1, description="Rules to audit against.")


@lru_cache
def load_catalog(referentiel: str) -> RuleCatalog:
    """Load and validate the catalog of a referential.

    The referential is checked against the known values before it is used to
    build a path, so it can never reach outside the rules directory.
    """
    try:
        known = Referentiel(referentiel)
    except ValueError as exc:
        raise PromptError(f"Unknown referential: '{referentiel}'.") from exc

    catalog_path = RULES_DIR / f"{known.value}.yaml"
    try:
        raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PromptError(f"No rule catalog for referential '{known.value}'.") from exc
    except yaml.YAMLError as exc:
        raise PromptError(f"Rule catalog for '{known.value}' is not valid YAML.") from exc

    try:
        catalog = RuleCatalog.model_validate(raw)
    except ValidationError as exc:
        raise PromptError(
            f"Rule catalog for '{known.value}' does not match the expected structure: {exc}"
        ) from exc

    if catalog.referentiel != known:
        raise PromptError(
            f"Rule catalog file '{catalog_path.name}' declares referential "
            f"'{catalog.referentiel.value}'."
        )

    seen: set[str] = set()
    for rule in catalog.rules:
        if rule.id in seen:
            raise PromptError(f"Duplicate rule id '{rule.id}' in catalog '{known.value}'.")
        seen.add(rule.id)

    return catalog


def referentiel_label(referentiel: str) -> str:
    """The human name of a referential, for anything a person reads.

    Falls back to the raw key rather than failing: a report is still worth
    producing when a catalog is missing its label.
    """
    if referentiel == UNSUPPORTED:
        return "Secteur non couvert"
    try:
        return load_catalog(referentiel).label
    except PromptError:
        logger.warning("No catalog for referential '%s'; showing the raw key", referentiel)
        return referentiel


def referentiel_description(referentiel: str) -> str:
    """One line describing what a referential covers, for the entry page."""
    try:
        return load_catalog(referentiel).description
    except PromptError:
        return ""


def render_rules(catalog: RuleCatalog) -> str:
    """Render a catalog as the rule block injected into the prompt."""
    return "\n\n".join(
        (
            f"- rule_id: {rule.id}\n"
            f"  requirement: {rule.title}\n"
            f"  default_severity: {rule.default_severity.value}\n"
            f"  deadline_days: {rule.deadline_days}\n"
            f"  iso_45001_clause: {rule.iso_45001_clause}"
        )
        for rule in catalog.rules
    )


@lru_cache
def _load_template() -> str:
    """Load the prompt template."""
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptError(f"Prompt template not found at {PROMPT_PATH}.") from exc


@lru_cache
def _load_detection() -> str:
    """Load the sector detection instructions."""
    try:
        return DETECTION_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptError(f"Detection template not found at {DETECTION_PATH}.") from exc


def supported_referentiels() -> list[str]:
    """The sectors the demonstration actually covers."""
    return [item.value for item in Referentiel]


def rule_ids(referentiel: str) -> set[str]:
    """Rule identifiers belonging to a referential, for checking a response."""
    try:
        return {rule.id for rule in load_catalog(referentiel).rules}
    except PromptError:
        return set()


def build_system_prompt(referentiel: str) -> str:
    """Build the audit prompt for a referential, catalog included."""
    catalog = load_catalog(referentiel)
    template = _load_template()

    for token in (REFERENTIEL_TOKEN, RULES_TOKEN):
        if token not in template:
            raise PromptError(f"Prompt template is missing the {token} placeholder.")

    return template.replace(REFERENTIEL_TOKEN, catalog.referentiel.value).replace(
        RULES_TOKEN, render_rules(catalog)
    )


def build_detection_prompt() -> str:
    """Build the prompt of the sector detection pass.

    Carries only what the catalogs declare about themselves — key, label and
    description — never their rules: the pass recognises an environment
    rather than auditing it, and shipping every rule to classify a photo
    would be paying for context nobody reads.
    """
    template = _load_detection()
    if SECTORS_TOKEN not in template:
        raise PromptError(f"Detection template is missing the {SECTORS_TOKEN} placeholder.")

    entries = []
    for name in supported_referentiels():
        catalog = load_catalog(name)
        entry = f'- "{name}" : {catalog.label}'
        if catalog.description:
            entry += f" — {catalog.description}"
        entries.append(entry)
    return template.replace(SECTORS_TOKEN, "\n".join(entries))
