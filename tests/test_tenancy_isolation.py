"""Cross-workspace isolation suite (spec §5.3, P8).

This suite BLOCKS DEPLOYMENT: deploy.sh and deploy.ps1 run it and abort on
failure. It attempts cross-workspace access at the data layer and against
every id-scoped endpoint: a record of another workspace must behave exactly
as if it did not exist.
"""

import pytest

from app.services import inspection_store

FOREIGN_WORKSPACE = "ws-foreign"


async def _seed_foreign_inspection(inspection_id: str = "foreign-1") -> str:
    """A finished inspection belonging to another tenant's workspace."""
    await inspection_store.set(
        FOREIGN_WORKSPACE,
        inspection_id,
        {
            "status": "done",
            "stage": "termine",
            "referentiel": "btp",
            "media_retained": False,
            "result": {
                "inspection_id": inspection_id,
                "referentiel": "btp",
                "scene_valid": True,
                "scene_detected": "A scene",
                "findings": [],
            },
            "error": None,
        },
    )
    return inspection_id


# --- data layer --------------------------------------------------------------


async def test_reads_are_scoped_at_the_store():
    inspection_id = await _seed_foreign_inspection()
    assert await inspection_store.get(FOREIGN_WORKSPACE, inspection_id) is not None
    assert await inspection_store.get("ws-default", inspection_id) is None
    assert await inspection_store.get("ws-third", inspection_id) is None


async def test_writes_are_scoped_at_the_store():
    inspection_id = await _seed_foreign_inspection()
    outcome = await inspection_store.update(
        "ws-default", inspection_id, status="failed"
    )
    assert outcome is None, "a cross-workspace write must not happen"
    record = await inspection_store.get(FOREIGN_WORKSPACE, inspection_id)
    assert record["status"] == "done", "the foreign record must be untouched"


async def test_the_store_refuses_unscoped_inspection_access():
    """The inspection API cannot be called without naming a workspace."""
    with pytest.raises(TypeError):
        await inspection_store.get("only-one-argument")  # type: ignore[call-arg]


# --- every id-scoped endpoint ------------------------------------------------

ENDPOINTS = [
    ("GET", "/inspections/{id}", None),
    ("GET", "/inspections/{id}/review", None),
    ("POST", "/inspections/{id}/findings/0/approve", None),
    ("POST", "/inspections/{id}/findings/0/reject", None),
    ("PATCH", "/inspections/{id}/findings/0", {"observed_severity": "mineur"}),
    (
        "POST",
        "/inspections/{id}/findings",
        {"rule_id": "BTP-01", "observation": "x", "observed_severity": "mineur"},
    ),
    ("POST", "/inspections/{id}/dispatch", None),
    ("GET", "/inspections/{id}/report.pdf", None),
    ("GET", "/inspections/{id}/evidence/image-00.jpg", None),
    ("POST", "/inspections/{id}/referentiel", {"referentiel": "btp"}),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
async def test_every_endpoint_denies_a_foreign_inspection(client, method, path, body):
    inspection_id = await _seed_foreign_inspection()
    response = client.request(
        method, path.format(id=inspection_id), json=body
    )
    assert response.status_code == 404, (
        f"{method} {path} answered {response.status_code} for a foreign "
        "inspection; it must behave as if the record did not exist"
    )


async def test_a_foreign_inspection_stays_untouched_after_the_attempts(client):
    inspection_id = await _seed_foreign_inspection("foreign-2")
    for method, path, body in ENDPOINTS:
        client.request(method, path.format(id=inspection_id), json=body)
    record = await inspection_store.get(FOREIGN_WORKSPACE, inspection_id)
    assert record["status"] == "done"
    assert record["result"]["findings"] == []
