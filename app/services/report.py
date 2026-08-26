"""French PDF report for one inspection."""

import logging
from datetime import date, datetime
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.schemas import (
    EnrichedFinding,
    EnrichedInspectionResult,
    FindingSource,
    Severity,
    ValidationStatus,
)
from app.services import inspection_prompt, storage

logger = logging.getLogger(__name__)

FOOTER = "Analyse assistée par IA, validée par un auditeur."

SEVERITY_LABEL: dict[str, str] = {
    Severity.ARRET_IMMEDIAT.value: "Arrêt immédiat",
    Severity.CRITIQUE.value: "Critique",
    Severity.MAJEUR.value: "Majeur",
    Severity.MINEUR.value: "Mineur",
}
SEVERITY_COLOR: dict[str, colors.Color] = {
    Severity.ARRET_IMMEDIAT.value: colors.HexColor("#b3261e"),
    Severity.CRITIQUE.value: colors.HexColor("#c2410c"),
    Severity.MAJEUR.value: colors.HexColor("#a16207"),
    Severity.MINEUR.value: colors.HexColor("#0f6f8f"),
}
SEVERITY_ORDER = [s.value for s in Severity]

_INK = colors.HexColor("#1a1d21")
_SOFT = colors.HexColor("#5c6470")
_LINE = colors.HexColor("#dfe3e8")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=17, leading=21,
                                alignment=TA_LEFT, textColor=_INK, spaceAfter=2),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=9.5, leading=13,
                              textColor=_SOFT),
        "h2": ParagraphStyle("h2", parent=base["Normal"], fontSize=12, leading=15,
                             textColor=_INK, fontName="Helvetica-Bold", spaceBefore=4),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10, leading=14,
                               textColor=_INK),
        "quote": ParagraphStyle("quote", parent=base["Normal"], fontSize=9, leading=12.5,
                                textColor=_SOFT, leftIndent=8),
        "label": ParagraphStyle("label", parent=base["Normal"], fontSize=8, leading=11,
                                textColor=_SOFT),
        "value": ParagraphStyle("value", parent=base["Normal"], fontSize=9, leading=12,
                                textColor=_INK),
        "badge": ParagraphStyle("badge", parent=base["Normal"], fontSize=8, leading=11,
                                textColor=_SOFT),
    }


def _format_datetime(moment: datetime | None) -> str:
    return moment.strftime("%d/%m/%Y à %H:%M") if moment else "non renseignée"


def retained_findings(result: EnrichedInspectionResult) -> list[EnrichedFinding]:
    """The findings this report may assert.

    Only what an auditor explicitly approved. A rejected finding, and one
    still awaiting a decision, are never reported: the report must not assert
    a validation that did not happen.
    """
    return [
        finding
        for finding in result.findings
        if finding.validation_status is ValidationStatus.APPROVED
    ]


def _origin_label(finding: EnrichedFinding) -> str:
    """How the finding got onto the record, in plain French."""
    if finding.source is FindingSource.HUMAN:
        return "Ajouté par l'auditeur"
    if finding.edited_by_human:
        return "Détecté par l'analyse, corrigé par l'auditeur"
    return "Détecté par l'analyse, validé par l'auditeur"


def _header(
    result: EnrichedInspectionResult, retained: list[EnrichedFinding], style: dict
) -> list:
    counts = {value: 0 for value in SEVERITY_ORDER}
    for finding in retained:
        counts[finding.observed_severity.value] = counts.get(finding.observed_severity.value, 0) + 1

    rejected = sum(
        1 for f in result.findings if f.validation_status is ValidationStatus.REJECTED
    )
    pending = sum(
        1 for f in result.findings if f.validation_status is ValidationStatus.PENDING
    )

    story = [
        Paragraph("Rapport d'inspection HSE", style["title"]),
        Paragraph(
            f"Référentiel : <b>{escape(inspection_prompt.referentiel_label(result.referentiel))}"
            f"</b> &nbsp;·&nbsp; Inspection {escape(result.inspection_id)}",
            style["sub"],
        ),
        Spacer(1, 8),
    ]

    rows = [
        ["Prise de vue", _format_datetime(result.captured_at)],
        ["Rapport édité le", date.today().strftime("%d/%m/%Y")],
        ["Scène analysée", result.scene_detected or "non renseignée"],
        ["Constats retenus", str(len(retained))],
    ]
    table = Table([[Paragraph(k, style["label"]), Paragraph(v, style["value"])] for k, v in rows],
                  colWidths=[38 * mm, 125 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, _LINE),
    ]))
    story.append(table)

    # The auditor's exclusions are stated, without asserting their content.
    excluded: list[str] = []
    if rejected:
        excluded.append(
            f"{rejected} constat{'s' if rejected > 1 else ''} "
            f"rejeté{'s' if rejected > 1 else ''} par l'auditeur, "
            "non retenu" + ("s" if rejected > 1 else "") + " dans ce rapport."
        )
    if pending:
        excluded.append(
            f"{pending} constat{'s' if pending > 1 else ''} en attente de validation, "
            "non retenu" + ("s" if pending > 1 else "") + " dans ce rapport."
        )
    if excluded:
        story.append(Spacer(1, 8))
        for line in excluded:
            story.append(Paragraph(line, style["sub"]))

    story.append(Spacer(1, 10))

    present = [(v, counts[v]) for v in SEVERITY_ORDER if counts.get(v)]
    if present:
        cells = [Paragraph(f"<b>{n}</b> {SEVERITY_LABEL[v]}", style["value"]) for v, n in present]
        chips = Table([cells], colWidths=[163 / max(len(cells), 1) * mm] * len(cells))
        chips.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.4, _LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, _LINE),
        ] + [("TEXTCOLOR", (i, 0), (i, 0), SEVERITY_COLOR[v]) for i, (v, _) in enumerate(present)]))
        story.append(chips)

    if any(f.immediate for f in retained):
        stop = Table([[Paragraph(
            "<b>ARRÊT IMMÉDIAT DE L'ACTIVITÉ</b><br/>"
            "Un ou plusieurs constats imposent l'arrêt immédiat des travaux concernés.",
            ParagraphStyle("stop", fontSize=10, leading=14, textColor=colors.white),
        )]], colWidths=[163 * mm])
        stop.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SEVERITY_COLOR[Severity.ARRET_IMMEDIAT.value]),
            ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.extend([Spacer(1, 10), stop])

    story.append(Spacer(1, 14))
    return story


def _evidence_flowable(inspection_id: str, finding: EnrichedFinding) -> Image | None:
    """The finding's evidence image, scaled to the page width."""
    if not finding.evidence_image:
        return None
    try:
        data = storage.get_evidence(inspection_id, finding.evidence_image)
        if not data:
            return None
        reader = ImageReader(BytesIO(data))
        width, height = reader.getSize()
        target = 90 * mm
        return Image(BytesIO(data), width=target, height=target * height / width)
    except Exception:  # noqa: BLE001 - a missing image must not break the report
        logger.warning("Could not embed evidence %s", finding.evidence_image, exc_info=True)
        return None


def _finding_section(
    inspection_id: str, index: int, finding: EnrichedFinding, style: dict
) -> list:
    severity = finding.observed_severity.value
    colour = SEVERITY_COLOR.get(severity, _SOFT)

    block: list = [
        HRFlowable(width="100%", thickness=2, color=colour, spaceAfter=6),
        Paragraph(
            f'<font color="#{colour.hexval()[2:]}" size="8"><b>'
            f"{SEVERITY_LABEL.get(severity, severity).upper()}</b></font>"
            f'  <font color="#868e9a" size="8">{finding.rule_id}</font>',
            style["badge"],
        ),
        Paragraph(f"{index + 1}. {finding.rule_title or finding.rule_id}", style["h2"]),
        Spacer(1, 4),
        Paragraph(finding.observation, style["body"]),
        Spacer(1, 5),
        Paragraph(f"<i>{finding.severity_reason}</i>", style["quote"]),
        Spacer(1, 8),
    ]

    picture = _evidence_flowable(inspection_id, finding)
    if picture is not None:
        block.extend([picture, Spacer(1, 8)])
    else:
        block.extend([Paragraph("Aucune image probante retenue pour ce constat.",
                                style["label"]), Spacer(1, 8)])

    rows = [
        ("Gravité retenue", SEVERITY_LABEL.get(severity, severity)),
        ("Échéance", finding.deadline_date.strftime("%d/%m/%Y")
         + (" — immédiat" if finding.immediate else "")),
        ("Responsable", finding.assigned_name or "Non affecté"),
        ("Clause ISO 45001", finding.iso_45001_clause or "—"),
        ("Origine", _origin_label(finding)),
    ]
    if finding.source is not FindingSource.HUMAN:
        rows.append(("Confiance de l'analyse", f"{round(finding.confidence * 100)}%"))
    if finding.edited_by_human and finding.original_severity is not None:
        rows.append(("Gravité initiale de l'analyse",
                     SEVERITY_LABEL.get(finding.original_severity.value,
                                        finding.original_severity.value)))
    if finding.edited_by_human and finding.original_observation:
        rows.append(("Observation initiale de l'analyse", finding.original_observation))

    table = Table([[Paragraph(k, style["label"]), Paragraph(v, style["value"])] for k, v in rows],
                  colWidths=[45 * mm, 118 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, _LINE),
    ]))
    block.extend([table, Spacer(1, 16)])
    return block


def _draw_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(_SOFT)
    canvas.drawString(20 * mm, 12 * mm, FOOTER)
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {canvas.getPageNumber()}")
    canvas.setStrokeColor(_LINE)
    canvas.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
    canvas.restoreState()


def build_pdf(result: EnrichedInspectionResult) -> bytes:
    """Render the inspection report and return the PDF bytes."""
    style = _styles()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=22 * mm,
        title=f"Rapport d'inspection {result.inspection_id}",
        author="Inspection HSE",
    )

    retained = retained_findings(result)
    story = _header(result, retained, style)
    if not retained:
        story.append(Paragraph("Aucune non-conformité retenue à l'issue de la validation.",
                               style["body"]))
    for index, finding in enumerate(retained):
        story.append(KeepTogether(_finding_section(result.inspection_id, index, finding, style)))

    document.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()


def report_filename(result: EnrichedInspectionResult) -> str:
    """File name offered for download and used as the email attachment name."""
    return f"rapport-inspection-{result.inspection_id}.pdf"
