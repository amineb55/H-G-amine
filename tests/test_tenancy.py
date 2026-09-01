"""Multi-tenancy: hierarchy, roles, journal, migration (spec §5, P8).

The cross-workspace ISOLATION suite lives in test_tenancy_isolation.py; this
module covers the model around it.
"""

from app.services import inspection_store, journal, tenancy
from app.services.tenancy import Action, Role, can


# --- permission matrix (spec §5.2) ------------------------------------------


def test_owner_holds_every_action():
    assert all(can(Role.OWNER, action) for action in Action)


def test_admin_manages_but_does_not_validate_or_bill():
    assert can(Role.ADMIN, Action.MANAGE_WORKSPACES)
    assert can(Role.ADMIN, Action.MANAGE_USERS)
    assert not can(Role.ADMIN, Action.VALIDATE_FINDINGS)
    assert not can(Role.ADMIN, Action.BILLING)
    assert not can(Role.ADMIN, Action.DELETE_ORGANISATION)


def test_consultant_reads_writes_audits_validates():
    for action in (Action.VIEW, Action.CREATE_INSPECTION, Action.VALIDATE_FINDINGS,
                   Action.RUN_AUDITS, Action.WRITE_DOCUMENTS, Action.DISPATCH):
        assert can(Role.CONSULTANT, action)
    assert not can(Role.CONSULTANT, Action.MANAGE_USERS)
    assert not can(Role.CONSULTANT, Action.BILLING)


def test_auditor_validates_but_does_not_manage():
    assert can(Role.AUDITOR, Action.VALIDATE_FINDINGS)
    assert can(Role.AUDITOR, Action.RUN_AUDITS)
    assert not can(Role.AUDITOR, Action.WRITE_DOCUMENTS)
    assert not can(Role.AUDITOR, Action.MANAGE_WORKSPACES)


def test_assignee_only_sees_and_treats_what_is_assigned():
    assert can(Role.ASSIGNEE, Action.VIEW)
    assert can(Role.ASSIGNEE, Action.TREAT_ASSIGNED)
    assert not can(Role.ASSIGNEE, Action.VALIDATE_FINDINGS)
    assert not can(Role.ASSIGNEE, Action.DISPATCH)


def test_reader_only_reads():
    assert can(Role.READER, Action.VIEW)
    for action in Action:
        if action is not Action.VIEW:
            assert not can(Role.READER, action), action


# --- bootstrap and migration -------------------------------------------------


async def test_default_organisation_and_workspace_are_created_idempotently():
    await tenancy.ensure_default()
    await tenancy.ensure_default()

    organisation = await inspection_store.get_document(
        tenancy.ORGANISATIONS_COLLECTION, tenancy.DEFAULT_ORGANISATION_ID
    )
    workspace = await inspection_store.get_document(
        tenancy.WORKSPACES_COLLECTION, tenancy.DEFAULT_WORKSPACE_ID
    )
    assert organisation is not None and organisation["name"]
    assert workspace is not None
    assert workspace["organisation_id"] == tenancy.DEFAULT_ORGANISATION_ID


async def test_pre_tenancy_records_belong_to_the_default_workspace():
    # A record stored before multi-tenancy carries no workspace field.
    await inspection_store.put_document(
        "inspections", "legacy-1", {"status": "done", "result": None, "error": None}
    )
    record = await inspection_store.get(tenancy.DEFAULT_WORKSPACE_ID, "legacy-1")
    assert record is not None, "legacy records must stay readable"
    assert await inspection_store.get("ws-other", "legacy-1") is None


async def test_adopt_unscoped_stamps_legacy_records_once():
    await inspection_store.put_document("inspections", "legacy-2", {"status": "done"})
    await inspection_store.set("ws-other", "scoped-1", {"status": "done"})

    assert await inspection_store.adopt_unscoped(tenancy.DEFAULT_WORKSPACE_ID) == 1
    record = await inspection_store.get(tenancy.DEFAULT_WORKSPACE_ID, "legacy-2")
    assert record["workspace_id"] == tenancy.DEFAULT_WORKSPACE_ID
    # Already-scoped records are left alone, and a second run adopts nothing.
    assert (await inspection_store.get("ws-other", "scoped-1"))["workspace_id"] == "ws-other"
    assert await inspection_store.adopt_unscoped(tenancy.DEFAULT_WORKSPACE_ID) == 0


# --- audit journal (spec §5.1, §7.3) -----------------------------------------


async def test_journal_entries_carry_actor_action_subject_and_time():
    await journal.record("ws-a", "someone", "finding.approved", "insp-1", index=2)
    entries = await journal.entries("ws-a")
    assert len(entries) == 1
    entry = entries[0]
    assert entry["actor"] == "someone"
    assert entry["action"] == "finding.approved"
    assert entry["subject"] == "insp-1"
    assert entry["details"] == {"index": 2}
    assert entry["at"]


async def test_journal_is_scoped_by_workspace():
    await journal.record("ws-a", "someone", "inspection.created", "insp-1")
    await journal.record("ws-b", "someone", "inspection.created", "insp-2")
    assert [e["subject"] for e in await journal.entries("ws-a")] == ["insp-1"]
    assert [e["subject"] for e in await journal.entries("ws-b")] == ["insp-2"]


def test_journal_is_append_only_by_construction():
    exposed = {name for name in dir(journal) if not name.startswith("_")}
    assert "record" in exposed and "entries" in exposed
    assert not {"update", "delete", "remove", "clear"} & exposed


async def test_human_actions_reach_the_journal(client, upload):
    inspection_id = upload().json()["inspection_id"]
    client.post(f"/inspections/{inspection_id}/findings/0/approve")
    client.post(f"/inspections/{inspection_id}/findings/1/reject")
    client.post(f"/inspections/{inspection_id}/dispatch")

    actions = [e["action"] for e in await journal.entries(tenancy.DEFAULT_WORKSPACE_ID)
               if e["subject"] == inspection_id]
    assert actions == [
        "inspection.created",
        "finding.approved",
        "finding.rejected",
        "inspection.dispatched",
    ]
