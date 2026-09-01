"""Characterization of the PDF report: only approved findings are retained."""

from helpers import make_finding, make_result

from app.models.schemas import ValidationStatus
from app.services import report


def _mixed_result():
    return make_result(
        [
            make_finding(observation="Approved one"),
            make_finding(
                observation="Approved two",
                validation_status=ValidationStatus.APPROVED,
            ),
            make_finding(
                observation="Rejected by the auditor",
                validation_status=ValidationStatus.REJECTED,
            ),
            make_finding(
                observation="Still awaiting a decision",
                validation_status=ValidationStatus.PENDING,
            ),
        ]
    )


def test_only_approved_findings_are_retained():
    retained = report.retained_findings(_mixed_result())
    assert len(retained) == 2
    assert {finding.observation for finding in retained} == {"Approved one", "Approved two"}


def test_pdf_builds_and_names_the_inspection():
    result = _mixed_result()
    pdf = report.build_pdf(result)
    assert pdf.startswith(b"%PDF"), "the report must be a real PDF"
    assert len(pdf) > 1000
    assert result.inspection_id in report.report_filename(result)


def test_pdf_endpoint_serves_the_report(client, upload):
    inspection_id = upload().json()["inspection_id"]
    response = client.get(f"/inspections/{inspection_id}/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_pdf_with_nothing_approved_still_builds():
    result = make_result(
        [make_finding(validation_status=ValidationStatus.REJECTED)]
    )
    # An auditor may legitimately want a report stating that nothing was
    # retained; producing it must not fail.
    assert report.build_pdf(result).startswith(b"%PDF")
