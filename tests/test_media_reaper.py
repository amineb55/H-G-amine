"""Retention of undetermined media is temporary by design: the sweep enforces it."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services import inspection_store, media_reaper, storage


async def _seed(hours_from_now: float, workspace_id: str = "ws-default") -> str:
    inspection_id = f"held-{uuid.uuid4().hex}"
    target = Path(storage.path(inspection_id))
    target.mkdir(parents=True)
    (target / "media.jpg").write_bytes(b"x")
    expiry = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    await inspection_store.set(
        workspace_id,
        inspection_id,
        {
            "status": "done",
            "media_retained": True,
            "media_expires_at": expiry.isoformat(),
        },
    )
    return inspection_id


async def test_expired_media_is_swept_and_unexpired_media_is_spared():
    # The sweep is maintenance across every workspace, by design.
    expired = await _seed(hours_from_now=-1, workspace_id="ws-other")
    fresh = await _seed(hours_from_now=+1)

    removed = await media_reaper.sweep_once()

    assert removed == 1
    assert not Path(storage.path(expired)).exists()
    assert Path(storage.path(fresh)).exists()

    expired_record = await inspection_store.get("ws-other", expired)
    assert expired_record["media_retained"] is False
    fresh_record = await inspection_store.get("ws-default", fresh)
    assert fresh_record["media_retained"] is True

    storage.delete_media(fresh)


async def test_unreadable_expiry_is_treated_as_expired():
    inspection_id = await _seed(hours_from_now=+1)
    await inspection_store.update("ws-default", inspection_id, media_expires_at="not-a-date")

    assert await media_reaper.sweep_once() == 1
    assert not Path(storage.path(inspection_id)).exists()
