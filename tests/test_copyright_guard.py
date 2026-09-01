"""Copyright guard (P6): no standard phrasing, ever.

This test must never be weakened to make content pass. A hit is fixed in the
content, or the pattern list is changed by the expert in
docs/expert/guard/motifs_interdits.yaml — not here.
"""

import pytest

from app.services.expert import check_exigences, load_bundle
from app.services.expert.models import Exigence

FILLER = (
    "Une méthode structurée, appliquée et tenue à jour, couvre les situations "
    "normales et anormales ainsi que les personnes présentes sur site. "
    "Les incidents passés alimentent la mise à jour, et la revue périodique "
    "laisse une trace datée exploitable en audit interne comme externe."
)


def _exigence(fr: str = FILLER, en: str = "", titre_fr: str = "Titre",
              titre_en: str = "Title") -> Exigence:
    return Exigence(
        id="45001-6.1.1", chapitre=6, titre_fr=titre_fr, titre_en=titre_en,
        exigence_fr=fr, exigence_en=en, type="documentaire",
        preuves_attendues=["p"], questions_audit=["q"], documents_types=[],
        hls_commun="non", equivalences=[], applicabilite="tous",
        regles_terrain=[], erreurs_frequentes="", poids=2,
    )


@pytest.fixture(scope="module")
def patterns():
    return load_bundle().guard_patterns


def test_the_delivered_content_passes_the_guard(patterns):
    report = check_exigences(load_bundle().exigences, patterns)
    assert report.errors == [], "\n".join(report.errors)


def test_the_pattern_list_comes_from_the_expert_file(patterns):
    assert "L'organisme doit" in patterns.interdits_fr
    assert "The organization shall" in patterns.interdits_en


def test_forbidden_french_phrasing_is_an_error(patterns):
    report = check_exigences(
        [_exigence(fr="L'organisme doit établir une méthode. " + FILLER)], patterns
    )
    assert any("L'organisme doit" in error for error in report.errors)


def test_obligation_modal_is_an_error_even_without_a_listed_pattern(patterns):
    report = check_exigences(
        [_exigence(fr="La méthode doit couvrir les situations. " + FILLER)], patterns
    )
    assert any("doit/doivent" in error for error in report.errors)


def test_standard_enumeration_is_an_error(patterns):
    report = check_exigences(
        [_exigence(fr=FILLER + "\na) premier point du texte normatif")], patterns
    )
    assert any("a)/b)" in error for error in report.errors)


def test_forbidden_english_phrasing_is_an_error(patterns):
    report = check_exigences(
        [_exigence(en="The organization shall establish a documented method.")],
        patterns,
    )
    assert any("The organization shall" in error for error in report.errors)


def test_titles_are_scanned_too(patterns):
    report = check_exigences(
        [_exigence(titre_fr="Ce que la présente norme attend")], patterns
    )
    assert any("titre_fr" in error for error in report.errors)


def test_phrasing_to_avoid_is_a_warning_not_an_error(patterns):
    report = check_exigences(
        [_exigence(fr=FILLER + " Les informations documentées sont disponibles.")],
        patterns,
    )
    assert report.errors == []
    assert any("informations documentées" in warning for warning in report.warnings)


def test_length_outside_the_window_is_a_warning(patterns):
    report = check_exigences([_exigence(fr="Trop court pour une exigence.")], patterns)
    assert report.errors == []
    assert any("characters" in warning for warning in report.warnings)


def test_clean_content_produces_no_findings(patterns):
    report = check_exigences([_exigence()], patterns)
    assert report.ok
    assert report.errors == []
