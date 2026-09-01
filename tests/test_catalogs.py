"""The rule and assignment catalogs stay coherent as data evolves."""

import re

from app.models.schemas import Referentiel, Severity
from app.services import assignment, inspection_prompt

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def test_each_rule_set_holds_twelve_well_formed_rules():
    for referentiel in Referentiel:
        catalog = inspection_prompt.load_catalog(referentiel.value)
        assert len(catalog.rules) == 12
        ids = [rule.id for rule in catalog.rules]
        assert len(set(ids)) == 12, f"duplicate rule ids in {referentiel.value}"
        for rule in catalog.rules:
            assert rule.title.strip()
            assert isinstance(rule.default_severity, Severity)
            assert rule.deadline_days >= 0


def test_catalogs_carry_a_label_and_description():
    for referentiel in Referentiel:
        assert inspection_prompt.referentiel_label(referentiel.value).strip()
        assert inspection_prompt.referentiel_description(referentiel.value).strip()


def test_unsupported_sector_still_has_a_label():
    assert inspection_prompt.referentiel_label(inspection_prompt.UNSUPPORTED).strip()


def test_every_rule_has_an_accountable_role():
    catalog = assignment.load_responsables()
    all_rule_ids = set()
    for referentiel in Referentiel:
        all_rule_ids |= inspection_prompt.rule_ids(referentiel.value)
    unassigned = all_rule_ids - set(catalog.assignments)
    assert not unassigned, f"rules with no accountable role: {sorted(unassigned)}"

    for role in catalog.roles.values():
        assert EMAIL.match(role.email)
        assert role.name.strip()
    assert catalog.escalation.arret_immediat_also_notifies in catalog.roles


def test_audit_prompt_is_fully_rendered_for_one_rule_set():
    prompt = inspection_prompt.build_system_prompt("btp")
    assert "{{" not in prompt, "no template token may survive rendering"
    for rule_id in inspection_prompt.rule_ids("btp"):
        assert rule_id in prompt
    # The audit prompt carries exactly one catalog: no cross-sector leakage.
    assert not any(rule_id in prompt for rule_id in inspection_prompt.rule_ids("bureaux"))


def test_detection_prompt_lists_sectors_but_no_rules():
    prompt = inspection_prompt.build_detection_prompt()
    assert "{{" not in prompt
    for referentiel in Referentiel:
        assert inspection_prompt.referentiel_label(referentiel.value) in prompt
    # Detection is the cheap pass: it must not embed the rule catalogs.
    assert "BTP-01" not in prompt
    assert "BUR-01" not in prompt


def test_supported_referentiels_matches_the_enum():
    assert set(inspection_prompt.supported_referentiels()) == {
        referentiel.value for referentiel in Referentiel
    }
