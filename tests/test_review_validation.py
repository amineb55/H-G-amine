"""Characterization of the human-validation surface: approve, reject, edit, add."""

from datetime import date, timedelta


def _done_inspection(client, upload) -> str:
    inspection_id = upload().json()["inspection_id"]
    assert client.get(f"/inspections/{inspection_id}").json()["status"] == "done"
    return inspection_id


def test_review_reports_counts_and_label(client, upload):
    inspection_id = _done_inspection(client, upload)
    review = client.get(f"/inspections/{inspection_id}/review").json()

    assert review["referentiel_label"], "the rule set must be shown by its human name"
    summary = review["summary"]
    assert summary["total"] == 3
    assert summary["pending"] == 3
    assert summary["requires_review"] == 1
    assert summary["has_immediate_stop"] is True


def test_approve_and_reject_record_the_decision(client, upload):
    inspection_id = _done_inspection(client, upload)

    approved = client.post(f"/inspections/{inspection_id}/findings/0/approve").json()
    assert approved["result"]["findings"][0]["validation_status"] == "approved"
    assert approved["summary"]["approved"] == 1

    rejected = client.post(f"/inspections/{inspection_id}/findings/2/reject").json()
    assert rejected["result"]["findings"][2]["validation_status"] == "rejected"
    assert rejected["result"]["findings"][2]["dispatch_status"] == "not_queued"
    assert rejected["summary"]["rejected"] == 1
    assert rejected["summary"]["pending"] == 1


def test_decisions_survive_a_reload(client, upload):
    inspection_id = _done_inspection(client, upload)
    client.post(f"/inspections/{inspection_id}/findings/1/approve")

    review = client.get(f"/inspections/{inspection_id}/review").json()
    assert review["result"]["findings"][1]["validation_status"] == "approved"


def test_validation_on_missing_finding_is_404(client, upload):
    inspection_id = _done_inspection(client, upload)
    assert client.post(f"/inspections/{inspection_id}/findings/99/approve").status_code == 404


def test_edit_keeps_the_original_and_recomputes(client, upload):
    inspection_id = _done_inspection(client, upload)

    edited = client.patch(
        f"/inspections/{inspection_id}/findings/1",
        json={"observed_severity": "arret_immediat"},
    ).json()

    # The edited finding jumps to the front: findings stay sorted by severity.
    moved = next(
        f for f in edited["result"]["findings"] if f["original_severity"] == "majeur"
    )
    assert moved["observed_severity"] == "arret_immediat"
    assert moved["edited_by_human"] is True
    assert moved["immediate"] is True
    assert moved["deadline_date"] == date.today().isoformat()


def test_edit_with_unknown_role_is_rejected(client, upload):
    inspection_id = _done_inspection(client, upload)
    response = client.patch(
        f"/inspections/{inspection_id}/findings/0", json={"assigned_role": "nobody"}
    )
    assert response.status_code == 400


def test_empty_edit_is_rejected(client, upload):
    inspection_id = _done_inspection(client, upload)
    assert client.patch(f"/inspections/{inspection_id}/findings/0", json={}).status_code == 400


def test_manual_finding_is_marked_human_and_assigned(client, upload):
    inspection_id = _done_inspection(client, upload)

    created = client.post(
        f"/inspections/{inspection_id}/findings",
        json={
            "rule_id": "BTP-02",
            "observation": "An unprotected floor opening next to the walkway.",
            "observed_severity": "critique",
        },
    )
    assert created.status_code == 201

    result = created.json()["result"]
    assert len(result["findings"]) == 4
    added = next(f for f in result["findings"] if f["source"] == "human")
    assert added["rule_id"] == "BTP-02"
    assert added["confidence"] == 1.0
    assert added["validation_status"] == "pending"
    assert added["deadline_date"] == (date.today() + timedelta(days=1)).isoformat()
    # Sorted in with the rest: critique lands after the immediate stop.
    assert [f["observed_severity"] for f in result["findings"]][:2] == [
        "arret_immediat",
        "critique",
    ]


def test_referentiel_options_expose_rules_and_roles(client):
    options = client.get("/referentiels/btp/options").json()
    assert len(options["rules"]) == 12
    assert {"id", "title", "default_severity"} <= set(options["rules"][0])
    assert options["roles"], "the review screen needs the role list"


def test_referentiels_listing_is_driven_by_the_catalogs(client):
    entries = client.get("/referentiels").json()
    keys = {entry["key"] for entry in entries}
    assert keys == {"btp", "bureaux"}
    for entry in entries:
        assert entry["label"]
        assert entry["description"]
