"""Deletion of media held for inspections whose sector was never chosen.

An inspection left undetermined keeps its media so the auditor can pick a
sector without uploading again. That hold is temporary by design: without a
sweep the retention promise would quietly become "kept indefinitely".
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.services import inspection_store, storage

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 900


def _expired(record: dict) -> bool:
    """Whether a retained media has outlived its hold."""
    raw = record.get("media_expires_at")
    if not raw:
        return False
    try:
        expiry = datetime.fromisoformat(str(raw))
    except ValueError:
        logger.warning("Unreadable media expiry %r; treating as expired", raw)
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= datetime.now(timezone.utc)


async def sweep_once() -> int:
    """Delete every retained media past its expiry. Returns how many went."""
    try:
        records = await inspection_store.list_retained()
    except Exception:  # noqa: BLE001 - a sweep must never take the app down
        logger.exception("Could not list inspections holding media")
        return 0

    removed = 0
    for workspace_id, inspection_id, record in records:
        if not _expired(record):
            continue
        try:
            storage.delete_media(inspection_id)
            await inspection_store.update(
                workspace_id, inspection_id, media_retained=False, media_expires_at=None
            )
            removed += 1
            logger.info("Deleted expired media for inspection %s", inspection_id)
        except Exception:  # noqa: BLE001 - one failure must not stop the sweep
            logger.exception("Could not delete expired media for %s", inspection_id)
    return removed


async def run_forever() -> None:
    """Sweep on a loop until cancelled."""
    while True:
        try:
            await sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the loop outlives any single failure
            logger.exception("Media sweep failed")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
