"""In-memory state for inspections.

Kept behind get/set/update so a database can replace the module body later
without touching callers. Records are copied in and out, so no caller holds a
reference to the stored state.
"""

import threading
from typing import Any

_LOCK = threading.Lock()
_RECORDS: dict[str, dict[str, Any]] = {}


def set(inspection_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Store a record, replacing any existing one, and return it."""
    with _LOCK:
        _RECORDS[inspection_id] = dict(record)
        return dict(_RECORDS[inspection_id])


def get(inspection_id: str) -> dict[str, Any] | None:
    """Return a record, or None when the inspection is unknown."""
    with _LOCK:
        record = _RECORDS.get(inspection_id)
        return dict(record) if record is not None else None


def update(inspection_id: str, **changes: Any) -> dict[str, Any] | None:
    """Apply changes to a record and return it, or None when unknown."""
    with _LOCK:
        record = _RECORDS.get(inspection_id)
        if record is None:
            return None
        record.update(changes)
        return dict(record)


def clear() -> None:
    """Drop every record. Intended for tests."""
    with _LOCK:
        _RECORDS.clear()
