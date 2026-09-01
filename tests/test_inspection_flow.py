"""End-to-end characterization of the inspection pipeline.

These tests pin the v0 behaviour of Service 3: upload, sector detection,
analysis, enrichment, media deletion, and every failure path. The analysis
engine is stubbed at its neutral interface; everything downstream of it is
the real code.
"""

from datetime import date, timedelta
from pathlib import Path

from app.services import storage


def _media_dir(inspection_id: str) -> Path:
    return Path(storage.path(inspection_id))


def test_forced_referentiel_runs_full_audit(client, upload, engine):
    response = upload(referentiel="btp")
    assert response.status_code == 202
    inspection_id = response.json()["inspection_id"]

    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "done"
    assert state["stage"] == "termine"
    assert state["error"] is None
    # A forced rule set skips detection entirely.
    assert engine.detect_calls == []
    assert state["detection"] is None

    result = state["result"]
    assert result["referentiel"] == "btp"
    severities = [f["observed_severity"] for f in result["findings"]]
    # Findings come back ordered most serious first.
    assert severities == ["arret_immediat", "majeur", "mineur"]


def test_findings_are_enriched_with_assignment_and_deadlines(client, upload):
    inspection_id = upload().json()["inspection_id"]
    findings = client.get(f"/inspections/{inspection_id}").json()["result"]["findings"]

    today = date.today()
    stop, major, minor = findings

    assert stop["immediate"] is True
    assert stop["deadline_date"] == today.isoformat()
    assert stop["notify_emails"], "an immediate-stop finding must have recipients"

    assert major["immediate"] is False
    assert major["deadline_date"] == (today + timedelta(days=7)).isoformat()
    # The low-confidence finding is flagged for review, never silently asserted.
    assert major["requires_review"] is True
    assert major["validation_status"] == "pending"

    assert minor["deadline_date"] == (today + timedelta(days=30)).isoformat()
    for finding in findings:
        assert finding["rule_title"], "catalog rules must contribute their title"
        assert finding["source"] == "ai"


def test_media_is_deleted_after_a_successful_audit(client, upload):
    inspection_id = upload().json()["inspection_id"]
    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "done"
    assert state["media_retained"] is False
    assert not _media_dir(inspection_id).exists()


def test_evidence_image_is_kept_and_served(client, upload):
    inspection_id = upload().json()["inspection_id"]
    findings = client.get(f"/inspections/{inspection_id}").json()["result"]["findings"]

    names = {f["evidence_image"] for f in findings}
    assert names == {"image-00.jpg"}
    assert storage.list_evidence(inspection_id) == ["image-00.jpg"]

    served = client.get(f"/inspections/{inspection_id}/evidence/image-00.jpg")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert served.content[:3] == b"\xff\xd8\xff"


def test_detection_runs_when_no_referentiel_is_given(client, upload, engine):
    engine.detection = {
        "referentiel": "bureaux",
        "confidence": 0.9,
        "justification": "Desks and workstations visible.",
    }
    inspection_id = upload(referentiel=None).json()["inspection_id"]

    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "done"
    assert state["detection"]["determined"] is True
    assert state["detection"]["referentiel"] == "bureaux"
    assert state["result"]["referentiel"] == "bureaux"
    assert state["media_retained"] is False
    assert len(engine.detect_calls) == 1
    assert engine.analyze_calls[0][1] == "bureaux"


def test_low_confidence_detection_never_audits(client, upload, engine):
    engine.detection = {
        "referentiel": "btp",
        "confidence": 0.4,
        "justification": "Context insufficient.",
    }
    inspection_id = upload(referentiel=None).json()["inspection_id"]

    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "done"
    assert state["detection"]["determined"] is False
    assert state["result"]["findings"] == []
    assert engine.analyze_calls == [], "no audit may run on an uncertain sector"
    # The media is held so the auditor can choose a sector without re-uploading.
    assert state["media_retained"] is True
    assert _media_dir(inspection_id).exists()


def test_undetermined_inspection_can_be_rerun_with_a_chosen_sector(client, upload, engine):
    engine.detection = {"referentiel": None, "confidence": 0.2, "justification": "Unclear."}
    inspection_id = upload(referentiel=None).json()["inspection_id"]
    assert client.get(f"/inspections/{inspection_id}").json()["media_retained"] is True

    chosen = client.post(
        f"/inspections/{inspection_id}/referentiel", json={"referentiel": "bureaux"}
    )
    assert chosen.status_code == 202

    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "done"
    assert state["result"]["referentiel"] == "bureaux"
    assert state["result"]["findings"], "the chosen sector must be audited"
    # The audit consumed the media: one exit path, whatever the outcome.
    assert state["media_retained"] is False
    assert not _media_dir(inspection_id).exists()


def test_choosing_a_sector_after_the_media_is_spent_conflicts(client, upload):
    inspection_id = upload().json()["inspection_id"]
    assert client.get(f"/inspections/{inspection_id}").json()["status"] == "done"

    response = client.post(
        f"/inspections/{inspection_id}/referentiel", json={"referentiel": "btp"}
    )
    assert response.status_code == 409


def test_analysis_failure_is_recorded_and_media_deleted(client, upload, engine):
    engine.fail_analysis = RuntimeError("The analysis engine could not be reached.")
    inspection_id = upload().json()["inspection_id"]

    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "failed"
    assert "could not be reached" in state["error"]
    assert state["result"] is None
    assert not _media_dir(inspection_id).exists()


def test_detection_failure_is_recorded_and_media_deleted(client, upload, engine):
    engine.fail_detection = RuntimeError("The analysis engine could not be reached.")
    inspection_id = upload(referentiel=None).json()["inspection_id"]

    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["status"] == "failed"
    assert not _media_dir(inspection_id).exists()


def test_unknown_inspection_is_404(client):
    assert client.get("/inspections/does-not-exist").status_code == 404
    assert client.get("/inspections/does-not-exist/review").status_code == 404


def test_mixed_video_and_images_are_rejected(client, jpeg_bytes):
    response = client.post(
        "/inspections",
        files=[
            ("files", ("a.jpg", jpeg_bytes, "image/jpeg")),
            ("files", ("b.mp4", b"not-a-real-video", "video/mp4")),
        ],
    )
    assert response.status_code == 400


def test_unsupported_media_type_is_rejected(client):
    response = client.post(
        "/inspections", files=[("files", ("a.gif", b"GIF89a", "image/gif"))]
    )
    assert response.status_code == 415


def test_too_many_images_are_rejected(upload):
    assert upload(count=11).status_code == 400


def test_oversized_upload_is_rejected_and_cleaned_up(client, jpeg_bytes, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_bytes", 10)
    response = client.post(
        "/inspections", files=[("files", ("a.jpg", jpeg_bytes, "image/jpeg"))]
    )
    assert response.status_code == 413
