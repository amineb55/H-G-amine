"""Append-only audit journal, per workspace (spec §5.1, §7.3; P1 groundwork).

Every human action on tenant data leaves an entry: who, what, on which
subject, when. The journal is immutable by construction — this module only
appends and reads; nothing here, and nothing elsewhere, updates or deletes an
entry.

Until authentication lands, the actor is a placeholder (debt D3 in
docs/DETTES.md); identity will supply the real one without changing callers.
"""

from datetime import datetime, timezone
from typing import Any

from app.services import inspection_store

JOURNAL_COLLECTION = "journal"


async def record(
    workspace_id: str, actor: str, action: str, subject: str, **details: Any
) -> str:
    """Append one entry and return its id.

    A failure propagates: an action that cannot be journalled is reported to
    the caller rather than silently unrecorded.
    """
    entry = {
        "workspace_id": workspace_id,
        "actor": actor,
        "action": action,
        "subject": subject,
        "at": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }
    return await inspection_store.add_document(JOURNAL_COLLECTION, entry)


async def entries(workspace_id: str) -> list[dict[str, Any]]:
    """Every entry of one workspace, oldest first."""
    rows = await inspection_store.list_documents(
        JOURNAL_COLLECTION, {"workspace_id": workspace_id}
    )
    return sorted((record for _entry_id, record in rows), key=lambda item: item["at"])
