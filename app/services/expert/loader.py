"""Loader for the expert's draft content.

The single entry point to everything under ``docs/expert``: no other module
reads those files (a test enforces it). A record that fails validation, a
duplicate id, or a reference to something that does not exist fails the load
loudly with the offending record named — draft content is either coherent or
rejected, never silently patched.

Everything that loads carries ``pending_validation`` and a watermark: it is
review material for the expert, and nothing here may reach a client-facing
path until the expert validates it.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.services.expert.guard import check_exigences
from app.services.expert.models import (
    ArbreDecision,
    Baremes,
    DocumentType,
    Exigence,
    FichierReglesTerrain,
    FormulaireCadrage,
    Glossaire,
    GuardPatterns,
    RegleTerrain,
)

PENDING_VALIDATION = "pending_validation"
WATERMARK = (
    "DRAFT — expert content pending validation. Review material only; "
    "must not appear in any client-facing output."
)

# Norm prefixes whose common-core requirements live on the 45001 records:
# a reference to one of their clause ids may have no record of its own.
_HLS_PREFIXES = ("9001-", "14001-", "50001-")

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "docs" / "expert"


class ExpertContentError(Exception):
    """The content is not loadable as-is. The message names every problem."""


@dataclass
class ExpertBundle:
    """Everything the expert delivered, validated and watermarked."""

    exigences: list[Exigence]
    regles_terrain: dict[str, list[RegleTerrain]]  # keyed by sector
    documents_types: dict[str, DocumentType]
    formulaire: FormulaireCadrage
    glossaire: Glossaire
    baremes: Baremes
    arbre_decision: ArbreDecision
    guard_patterns: GuardPatterns
    status: str = PENDING_VALIDATION
    watermark: str = WATERMARK
    warnings: list[str] = field(default_factory=list)


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExpertContentError(f"Missing expert file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ExpertContentError(f"{path} is not valid YAML: {exc}") from exc


def _validation_lines(source: str, exc: ValidationError) -> list[str]:
    lines = []
    for problem in exc.errors():
        location = ".".join(str(part) for part in problem["loc"]) or "(record)"
        lines.append(f"{source}: {location}: {problem['msg']}")
    return lines


def _app_rule_ids() -> set[str]:
    """Rule ids of the catalogs already shipped with the application."""
    from app.services import inspection_prompt

    ids: set[str] = set()
    for referentiel in inspection_prompt.supported_referentiels():
        ids |= inspection_prompt.rule_ids(referentiel)
    return ids


def _cross_reference(
    exigences: list[Exigence],
    regles_by_secteur: dict[str, list[RegleTerrain]],
    documents_types: dict[str, DocumentType],
    formulaire: FormulaireCadrage,
) -> tuple[list[str], list[str]]:
    """Every reference must point at something that exists."""
    errors: list[str] = []
    warnings: list[str] = []

    exigence_ids = {e.id for e in exigences}
    expert_rule_ids = {
        regle.id for regles in regles_by_secteur.values() for regle in regles
    }
    known_rule_ids = expert_rule_ids | _app_rule_ids()

    for exigence in exigences:
        for slug in exigence.documents_types:
            if slug not in documents_types:
                errors.append(f"{exigence.id}: unknown document type '{slug}'")
        for rule_id in exigence.regles_terrain:
            if rule_id not in known_rule_ids:
                errors.append(f"{exigence.id}: unknown field rule '{rule_id}'")
        if exigence.nuance_de and exigence.nuance_de not in exigence_ids:
            errors.append(
                f"{exigence.id}: nuance_de points at unknown record '{exigence.nuance_de}'"
            )
        for other in exigence.equivalences:
            if other not in exigence_ids:
                warnings.append(
                    f"{exigence.id}: equivalence {other} has no record of its own "
                    "(HLS requirement carried by the 45001 common core)"
                )

    for secteur, regles in regles_by_secteur.items():
        for regle in regles:
            for exigence_id in regle.exigences:
                if exigence_id not in exigence_ids:
                    errors.append(
                        f"{regle.id} ({secteur}): unknown requirement '{exigence_id}'"
                    )
            if len(regle.indices_visuels) < 3:
                warnings.append(f"{regle.id}: fewer than 3 visual cues")
            if len(regle.exclusions) < 2:
                warnings.append(f"{regle.id}: fewer than 2 exclusions")

    for question in formulaire.questions:
        for slug in question.documents:
            if slug not in documents_types:
                errors.append(f"{question.id}: unknown document type '{slug}'")
        for exigence_id in question.exigences:
            if exigence_id in exigence_ids:
                continue
            if exigence_id.startswith(_HLS_PREFIXES):
                warnings.append(
                    f"{question.id}: requirement {exigence_id} carried by the "
                    "45001 common core"
                )
            else:
                errors.append(f"{question.id}: unknown requirement '{exigence_id}'")

    return errors, warnings


def load_bundle(root: Path | None = None) -> ExpertBundle:
    """Load, validate and cross-check everything under ``docs/expert``.

    Raises ``ExpertContentError`` naming every offending record when the
    content is not coherent. Warnings — review pointers, not blockers — are
    returned on the bundle.
    """
    base = Path(root) if root is not None else DEFAULT_ROOT
    errors: list[str] = []

    # Requirements: every exigences_*.yaml file, order-stable.
    exigences: list[Exigence] = []
    seen_ids: set[str] = set()
    for path in sorted((base / "exigences").glob("exigences_*.yaml")):
        for raw in _read_yaml(path) or []:
            record_id = raw.get("id", "?") if isinstance(raw, dict) else "?"
            try:
                exigence = Exigence.model_validate(raw)
            except ValidationError as exc:
                errors.extend(_validation_lines(f"{path.name}:{record_id}", exc))
                continue
            if exigence.id in seen_ids:
                errors.append(f"{path.name}: duplicate requirement id '{exigence.id}'")
                continue
            seen_ids.add(exigence.id)
            exigences.append(exigence)
    if not exigences:
        errors.append(f"No requirement records found under {base / 'exigences'}")

    # Master list of document slugs.
    documents_types: dict[str, DocumentType] = {}
    raw_types = _read_yaml(base / "exigences" / "documents_types.yaml") or {}
    for slug, raw in raw_types.items():
        try:
            documents_types[slug] = DocumentType.model_validate(raw)
        except ValidationError as exc:
            errors.extend(_validation_lines(f"documents_types.yaml:{slug}", exc))

    # Sector rule sets.
    regles_by_secteur: dict[str, list[RegleTerrain]] = {}
    seen_rules: set[str] = set()
    for path in sorted((base / "regles_terrain").glob("*.yaml")):
        try:
            fichier = FichierReglesTerrain.model_validate(_read_yaml(path))
        except ValidationError as exc:
            errors.extend(_validation_lines(path.name, exc))
            continue
        for regle in fichier.regles:
            if regle.id in seen_rules:
                errors.append(f"{path.name}: duplicate rule id '{regle.id}'")
        seen_rules |= {regle.id for regle in fichier.regles}
        regles_by_secteur[fichier.secteur] = fichier.regles

    # Framing form, glossary, scales, decision tree, guard patterns.
    def _load_model(model, path: Path):
        try:
            return model.model_validate(_read_yaml(path))
        except ValidationError as exc:
            errors.extend(_validation_lines(path.name, exc))
            return None

    formulaire = _load_model(FormulaireCadrage, base / "formulaire" / "questions_cadrage.yaml")
    if formulaire is not None:
        question_ids = [question.id for question in formulaire.questions]
        for duplicate in {q for q in question_ids if question_ids.count(q) > 1}:
            errors.append(f"questions_cadrage.yaml: duplicate question id '{duplicate}'")

    glossaire = _load_model(Glossaire, base / "glossaire" / "glossaire_fr_en.yaml")
    baremes = _load_model(Baremes, base / "baremes" / "baremes.yaml")
    arbre = _load_model(ArbreDecision, base / "outils_qualite" / "arbre_decision.yaml")
    patterns = _load_model(GuardPatterns, base / "guard" / "motifs_interdits.yaml")

    if errors:
        raise ExpertContentError(
            "Expert content failed validation:\n" + "\n".join(sorted(errors))
        )
    assert formulaire and glossaire and baremes and arbre and patterns  # for typing

    cross_errors, warnings = _cross_reference(
        exigences, regles_by_secteur, documents_types, formulaire
    )

    guard_report = check_exigences(exigences, patterns)
    cross_errors.extend(guard_report.errors)
    warnings.extend(guard_report.warnings)

    if cross_errors:
        raise ExpertContentError(
            "Expert content failed validation:\n" + "\n".join(sorted(cross_errors))
        )

    return ExpertBundle(
        exigences=exigences,
        regles_terrain=regles_by_secteur,
        documents_types=documents_types,
        formulaire=formulaire,
        glossaire=glossaire,
        baremes=baremes,
        arbre_decision=arbre,
        guard_patterns=patterns,
        warnings=warnings,
    )
