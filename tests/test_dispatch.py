"""Characterization of email dispatch: grouping, ordering, idempotence, isolation."""

import asyncio

from helpers import make_finding, make_result

from app.models.schemas import (
    DispatchStatus,
    EmailKind,
    Severity,
    ValidationStatus,
)
from app.services import notification


def _prepared_inspection(client, upload) -> str:
    """A finished inspection with the stop and the major finding approved."""
    inspection_id = upload().json()["inspection_id"]
    client.post(f"/inspections/{inspection_id}/findings/0/approve")
    client.post(f"/inspections/{inspection_id}/findings/1/approve")
    client.post(f"/inspections/{inspection_id}/findings/2/reject")
    return inspection_id


def test_dispatch_with_nothing_approved_sends_nothing(client, upload, outbox):
    inspection_id = upload().json()["inspection_id"]
    response = client.post(f"/inspections/{inspection_id}/dispatch").json()
    assert response["sent"] is False
    assert response["emails"] == []
    assert outbox.sent == []


def test_dispatch_sends_immediate_alert_first_with_report_attached(client, upload, outbox):
    inspection_id = _prepared_inspection(client, upload)
    response = client.post(f"/inspections/{inspection_id}/dispatch").json()

    assert response["sent"] is True
    assert response["failed_count"] == 0
    kinds = [outcome["kind"] for outcome in response["emails"]]
    assert kinds[0] == "immediate", "the immediate-stop alert goes out first"
    assert response["emails"][0]["subject"].startswith("[IMMEDIATE STOP]")

    assert outbox.sent, "the notifier interface must have been called"
    for email in outbox.sent:
        names = [name for name, _payload in email["attachments"]]
        assert any(name.endswith(".pdf") for name in names), "every email carries the report"
    # The finding approved from a low-confidence review is called out.
    assert response["approved_from_review"], "review-flagged findings are reported on dispatch"


def test_rejected_findings_are_never_dispatched(client, upload, outbox):
    inspection_id = _prepared_inspection(client, upload)
    response = client.post(f"/inspections/{inspection_id}/dispatch").json()

    carried = {
        index for email in response["emails"] for index in email["finding_indexes"]
    }
    assert carried == {0, 1}, "only approved findings may be carried"
    state = client.get(f"/inspections/{inspection_id}").json()
    assert state["result"]["findings"][2]["dispatch_status"] == "not_queued"


def test_dispatch_is_idempotent(client, upload, outbox):
    inspection_id = _prepared_inspection(client, upload)
    first = client.post(f"/inspections/{inspection_id}/dispatch").json()
    assert first["sent_count"] > 0
    sent_before = len(outbox.sent)

    second = client.post(f"/inspections/{inspection_id}/dispatch").json()
    assert second["sent_count"] == 0
    assert sorted(second["already_sent"]) == [0, 1]
    assert len(outbox.sent) == sent_before, "a finding already sent is never sent twice"


def test_dispatch_records_message_id_on_each_finding(client, upload, outbox):
    inspection_id = _prepared_inspection(client, upload)
    client.post(f"/inspections/{inspection_id}/dispatch")

    findings = client.get(f"/inspections/{inspection_id}").json()["result"]["findings"]
    for index in (0, 1):
        assert findings[index]["dispatch_status"] == "sent"
        assert findings[index]["message_id"]


def test_cc_addresses_are_validated_and_copied(client, upload, outbox):
    inspection_id = _prepared_inspection(client, upload)

    bad = client.post(
        f"/inspections/{inspection_id}/dispatch", json={"cc": ["not-an-address"]}
    )
    assert bad.status_code == 422
    assert outbox.sent == []

    good = client.post(
        f"/inspections/{inspection_id}/dispatch", json={"cc": ["copy@example.test"]}
    ).json()
    assert good["sent"] is True
    for email in outbox.sent:
        assert email["cc"] == ["copy@example.test"]


def test_is_notifiable_requires_approval_and_recipients():
    assert notification.is_notifiable(make_finding()) is True
    assert notification.is_notifiable(
        make_finding(validation_status=ValidationStatus.PENDING)
    ) is False
    assert notification.is_notifiable(
        make_finding(validation_status=ValidationStatus.REJECTED)
    ) is False
    assert notification.is_notifiable(
        make_finding(dispatch_status=DispatchStatus.SENT)
    ) is False
    assert notification.is_notifiable(make_finding(notify_emails=[])) is False


def test_grouping_fans_out_to_every_recipient():
    result = make_result(
        [
            make_finding(notify_emails=["a@example.test", "b@example.test"]),
            make_finding(
                observed_severity=Severity.ARRET_IMMEDIAT,
                immediate=True,
                notify_emails=["a@example.test"],
            ),
        ]
    )
    groups = notification.group_by_recipient(result)
    assert groups == {
        ("a@example.test", EmailKind.DIGEST): [0],
        ("b@example.test", EmailKind.DIGEST): [0],
        ("a@example.test", EmailKind.IMMEDIATE): [1],
    }


async def test_one_failed_email_never_undoes_a_sent_one(outbox):
    result = make_result(
        [
            make_finding(notify_emails=["works@example.test"]),
            make_finding(notify_emails=["broken@example.test"]),
        ]
    )
    outbox.fail_for = {"broken@example.test"}

    outcomes = await notification.dispatch(result)

    by_address = {outcome.email: outcome for outcome in outcomes}
    assert by_address["works@example.test"].status is DispatchStatus.SENT
    assert by_address["broken@example.test"].status is DispatchStatus.FAILED
    assert by_address["broken@example.test"].error

    assert result.findings[0].dispatch_status is DispatchStatus.SENT
    assert result.findings[1].dispatch_status is DispatchStatus.FAILED
    assert result.findings[1].dispatch_error
