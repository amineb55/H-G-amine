"""The expert content loads validated, watermarked, and structurally blocked.

Spec §3.4 and the expert handover brief: strict loaders (unknown field,
duplicate id, unknown cross-reference all fail loudly, naming the record),
content marked pending validation, and nothing outside the loader package
reading the files.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

import yaml

from app.services.expert import (
    PENDING_VALIDATION,
    ExpertContentError,
    load_bundle,
)
from app.services.expert.loader import _cross_reference
from app.services.expert.models import (
    Exigence,
    FormulaireCadrage,
    QuestionCadrage,
    RegleTerrain,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERT_ROOT = PROJECT_ROOT / "docs" / "expert"


def _exigence_raw(**overrides) -> dict:
    base = dict(
        id="45001-6.1.1",
        chapitre=6,
        titre_fr="Titre",
        titre_en="Title",
        exigence_fr="L'état attendu, décrit dans les mots de l'expert." * 6,
        exigence_en="",
        type="documentaire",
        preuves_attendues=["Une preuve"],
        questions_audit=["Une question ?"],
        documents_types=["analyse_contexte"],
        hls_commun="oui",
        equivalences=[],
        applicabilite="tous",
        regles_terrain=[],
        erreurs_frequentes="Ce qui rate le plus souvent.",
        poids=2,
    )
    base.update(overrides)
    return base


# --- the real delivered content ---------------------------------------------


def test_the_delivered_drafts_load_completely():
    bundle = load_bundle()
    assert len(bundle.exigences) == 123
    assert sum(len(rules) for rules in bundle.regles_terrain.values()) == 72
    assert len(bundle.regles_terrain) == 6
    assert len(bundle.documents_types) == 136
    assert len(bundle.formulaire.questions) == 88
    assert len(bundle.glossaire.termes) == 121
    assert bundle.baremes.criticite_constats.plafond == 4
    assert bundle.arbre_decision.branches


def test_everything_loaded_is_pending_validation_and_watermarked():
    bundle = load_bundle()
    assert bundle.status == PENDING_VALIDATION
    assert "pending validation" in bundle.watermark
    assert "client-facing" in bundle.watermark


def test_hls_equivalences_are_warnings_not_errors():
    bundle = load_bundle()
    assert bundle.warnings, "the HLS common core must surface as review warnings"
    assert all("common core" in warning or "visual cues" in warning
               or "exclusions" in warning for warning in bundle.warnings)


# --- strictness, demonstrated on synthetic records ---------------------------


def test_unknown_field_is_refused():
    with pytest.raises(ValidationError, match="invente"):
        Exigence.model_validate(_exigence_raw(invente="?"))


def test_bad_weight_and_type_are_refused():
    with pytest.raises(ValidationError):
        Exigence.model_validate(_exigence_raw(poids=4))
    with pytest.raises(ValidationError, match="unknown type"):
        Exigence.model_validate(_exigence_raw(type="obligatoire"))


def test_hls_flag_accepts_only_oui_or_non():
    with pytest.raises(ValidationError, match="oui"):
        Exigence.model_validate(_exigence_raw(hls_commun="peut-etre"))


def test_rule_requires_visual_cues():
    with pytest.raises(ValidationError):
        RegleTerrain.model_validate(
            dict(
                id="IND-99", titre="t", categorie="c", description="d",
                criticite_defaut=3, exigences=["45001-6.1.1"],
                reference_reglementaire="", indices_visuels=[], exclusions=[],
                action_immediate="",
            )
        )


def _empty_form() -> FormulaireCadrage:
    return FormulaireCadrage(
        version="test", sections={1: "s"}, seuil_minimal_regle="r",
        questions=[
            QuestionCadrage(
                id="Q01", section=1, secteur="tous", norme="tous",
                seuil_minimal="non", type_reponse="texte", question="?",
                documents=[], exigences=[], pourquoi="aide",
            )
        ],
    )


def test_unknown_references_are_errors_naming_the_record():
    exigence = Exigence.model_validate(
        _exigence_raw(
            documents_types=["slug_inconnu"],
            regles_terrain=["ZZZ-99"],
            nuance_de="45001-0.0",
        )
    )
    errors, _warnings = _cross_reference([exigence], {}, {}, _empty_form())
    text = "\n".join(errors)
    assert "45001-6.1.1: unknown document type 'slug_inconnu'" in text
    assert "45001-6.1.1: unknown field rule 'ZZZ-99'" in text
    assert "nuance_de points at unknown record '45001-0.0'" in text


def test_rule_referencing_unknown_requirement_is_an_error():
    regle = RegleTerrain.model_validate(
        dict(
            id="IND-98", titre="t", categorie="c", description="d",
            criticite_defaut=2, exigences=["45001-0.0"],
            reference_reglementaire="", indices_visuels=["un", "deux", "trois"],
            exclusions=["a", "b"], action_immediate="",
        )
    )
    errors, _warnings = _cross_reference([], {"industrie": [regle]}, {}, _empty_form())
    assert any("IND-98" in error and "45001-0.0" in error for error in errors)


def test_existing_app_rule_ids_are_valid_references():
    exigence = Exigence.model_validate(_exigence_raw(regles_terrain=["BTP-01", "BUR-02"]))
    errors, _warnings = _cross_reference([exigence], {}, {"analyse_contexte": None}, _empty_form())
    assert not [error for error in errors if "field rule" in error]


def test_a_corrupted_tree_fails_naming_the_record(tmp_path):
    import shutil

    root = tmp_path / "expert"
    shutil.copytree(EXPERT_ROOT, root)
    broken = dict(
        secteur="test", version="0", regles=[
            dict(
                id="TST-01", titre="t", categorie="c", description="d",
                criticite_defaut=2, exigences=["45001-0.0"],
                reference_reglementaire="", indices_visuels=["a", "b", "c"],
                exclusions=["a", "b"], action_immediate="",
            )
        ],
    )
    (root / "regles_terrain" / "test.yaml").write_text(
        yaml.safe_dump(broken, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(ExpertContentError, match="TST-01"):
        load_bundle(root)


# --- structural block: pending content cannot reach a client path ------------


def test_no_application_module_imports_the_expert_package():
    """Until a validation workflow exists, the only importers may be tests."""
    importers = []
    for path in sorted(PROJECT_ROOT.glob("app/**/*.py")):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if relative.startswith("app/services/expert/"):
            continue
        if "app.services.expert" in path.read_text(encoding="utf-8"):
            importers.append(relative)
    assert importers == [], (
        "pending-validation content is blocked from the application: "
        f"unexpected importers {importers}"
    )


def test_only_the_loader_package_reads_the_expert_files():
    readers = []
    for path in sorted(PROJECT_ROOT.glob("app/**/*.py")):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if relative.startswith("app/services/expert/"):
            continue
        if "docs/expert" in path.read_text(encoding="utf-8"):
            readers.append(relative)
    assert readers == []
