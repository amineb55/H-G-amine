"""Copyright guard (principle P6).

Requirements describe the state an auditor observes, never the standard's own
wording. This module flags standard-like phrasing using the pattern list the
expert maintains in ``docs/expert/guard/motifs_interdits.yaml``, plus the
complementary rules documented in that file: no obligation modal in a
requirement text, no reproduction of the standard's internal a) b) c)
numbering, and a length window that discourages both copying and padding.

This guard must never be weakened to make content pass: a hit is fixed in the
content, or the pattern list is changed by the expert — not here.
"""

import re
from dataclasses import dataclass, field

from app.services.expert.models import Exigence, GuardPatterns

# " doit " / " doivent " as words: the injunction form of a standard.
_MODAL = re.compile(r"\b(doit|doivent)\b")
# A line starting like the standard's own internal enumeration.
_ENUMERATION = re.compile(r"^\s*[a-h]\)", re.MULTILINE)

LENGTH_MIN = 250
LENGTH_MAX = 900


@dataclass
class GuardReport:
    """What the guard found. ``errors`` block; ``warnings`` inform review."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_exigences(exigences: list[Exigence], patterns: GuardPatterns) -> GuardReport:
    """Run every rule of the guard over every requirement record."""
    report = GuardReport()

    for exigence in exigences:
        fr_fields = {"titre_fr": exigence.titre_fr, "exigence_fr": exigence.exigence_fr}
        en_fields = {"titre_en": exigence.titre_en, "exigence_en": exigence.exigence_en}

        for name, text in fr_fields.items():
            for motif in patterns.interdits_fr:
                if motif in text:
                    report.errors.append(
                        f"{exigence.id}: forbidden phrasing « {motif} » in {name}"
                    )
        for name, text in en_fields.items():
            for motif in patterns.interdits_en:
                if motif in text:
                    report.errors.append(
                        f"{exigence.id}: forbidden phrasing « {motif} » in {name}"
                    )

        if _MODAL.search(exigence.exigence_fr):
            report.errors.append(
                f"{exigence.id}: obligation modal « doit/doivent » in exigence_fr — "
                "describe the observed state, not the injunction"
            )
        if _ENUMERATION.search(exigence.exigence_fr):
            report.errors.append(
                f"{exigence.id}: a)/b) enumeration in exigence_fr reproduces the "
                "standard's internal numbering"
            )

        length = len(exigence.exigence_fr)
        if not LENGTH_MIN <= length <= LENGTH_MAX:
            report.warnings.append(
                f"{exigence.id}: exigence_fr is {length} characters "
                f"(target {LENGTH_MIN}-{LENGTH_MAX})"
            )

        for motif in patterns.a_eviter_fr:
            if motif in exigence.exigence_fr:
                report.warnings.append(
                    f"{exigence.id}: phrasing to avoid « {motif} » in exigence_fr"
                )
        for motif in patterns.a_eviter_en:
            if motif in exigence.exigence_en:
                report.warnings.append(
                    f"{exigence.id}: phrasing to avoid « {motif} » in exigence_en"
                )

    return report
