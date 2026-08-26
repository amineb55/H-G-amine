"""Persistent state for inspections.

Backed by a document database so an inspection survives a restart, with an
in-memory backend for local work without credentials (``STORE_BACKEND=memory``).

The interface is ``get`` / ``set`` / ``update``, keyed by inspection id.
Records are copied in and out, so no caller holds a reference to stored state.
The database client is synchronous, so every call runs in a worker thread and
the event loop is never blocked.
"""

import asyncio
import logging
import threading
from datetime import date, datetime
from enum import Enum
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

MEMORY_BACKEND = "memory"

_LOCK = threading.Lock()
_RECORDS: dict[str, dict[str, Any]] = {}

_client: Any = None
_client_lock = threading.Lock()


class StoreError(Exception):
    """A storage failure, already phrased for the person reading it."""


def backend() -> str:
    """Which backend is in use."""
    return get_settings().store_backend.strip().lower()


def _encode(value: Any) -> Any:
    """Make a value safe to store: enums and dates become plain scalars."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    return value


def _get_client() -> Any:
    """Return the database client, building it on first use.

    Never called at import time: a database that is unreachable must not stop
    the application from starting.
    """
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        try:
            from google.cloud import firestore
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise StoreError(
                "The storage client is not installed. Install the project "
                "dependencies, or set STORE_BACKEND=memory."
            ) from exc

        project = get_settings().store_project_id.strip()
        try:
            # No key file: credentials come from the ambient environment.
            _client = firestore.Client(project=project) if project else firestore.Client()
        except Exception as exc:  # noqa: BLE001 - translated for the caller
            raise StoreError(f"Could not reach the inspection store: {exc}") from exc
        return _client


def _collection() -> Any:
    return _get_client().collection(get_settings().store_collection)


def _deadline() -> float:
    """Per-operation deadline, so a slow store never hangs a request."""
    return get_settings().store_timeout_seconds


def _as_store_error(exc: Exception, action: str) -> StoreError:
    """Translate a client failure into a message worth showing."""
    name = exc.__class__.__name__
    if name in ("PermissionDenied", "Unauthenticated"):
        return StoreError(
            "The inspection store rejected the credentials. Check that "
            "application default credentials are available."
        )
    if name in ("NotFound",):
        return StoreError(
            "The inspection store or its database does not exist for this project."
        )
    if name in ("DeadlineExceeded", "ServiceUnavailable", "RetryError"):
        return StoreError("The inspection store is unreachable. Retry in a moment.")
    return StoreError(f"The inspection store could not {action}: {exc}")


# --- synchronous bodies, each run in a worker thread ------------------------


def _set_sync(inspection_id: str, record: dict[str, Any]) -> dict[str, Any]:
    payload = _encode(record)
    try:
        _collection().document(inspection_id).set(payload, timeout=_deadline())
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "store this inspection") from exc
    return dict(payload)


def _get_sync(inspection_id: str) -> dict[str, Any] | None:
    try:
        snapshot = _collection().document(inspection_id).get(timeout=_deadline())
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "read this inspection") from exc
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def _update_sync(inspection_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    payload = _encode(changes)
    document = _collection().document(inspection_id)
    try:
        snapshot = document.get(timeout=_deadline())
        if not snapshot.exists:
            return None
        # Written as a merge so a concurrent change to another field survives.
        document.set(payload, merge=True, timeout=_deadline())
        record = snapshot.to_dict() or {}
        record.update(payload)
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "update this inspection") from exc
    return record


def _clear_sync() -> None:
    try:
        for document in _collection().list_documents(timeout=_deadline()):
            document.delete()
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "clear the inspections") from exc


async def _run(action: str, function: Any, *args: Any) -> Any:
    """Run a store call in a worker thread under a hard deadline.

    The client library retries internally and can outlive its own timeout, so
    the deadline is enforced here. A thread cannot be interrupted: a straggler
    is left to finish on its own rather than holding up the request.
    """
    task = asyncio.ensure_future(asyncio.to_thread(function, *args))
    done, _pending = await asyncio.wait({task}, timeout=_deadline())
    if not done:
        raise StoreError(
            f"The inspection store did not answer in time; could not {action}."
        )
    error = task.exception()
    if error is not None:
        raise error
    return task.result()


# --- public interface -------------------------------------------------------


async def set(inspection_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Store a record, replacing any existing one, and return it."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            _RECORDS[inspection_id] = _encode(record)
            return dict(_RECORDS[inspection_id])
    return await _run("store this inspection", _set_sync, inspection_id, record)


async def get(inspection_id: str) -> dict[str, Any] | None:
    """Return a record, or None when the inspection is unknown."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            record = _RECORDS.get(inspection_id)
            return dict(record) if record is not None else None
    return await _run("read this inspection", _get_sync, inspection_id)


async def update(inspection_id: str, **changes: Any) -> dict[str, Any] | None:
    """Apply changes to a record and return it, or None when unknown."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            record = _RECORDS.get(inspection_id)
            if record is None:
                return None
            record.update(_encode(changes))
            return dict(record)
    return await _run("update this inspection", _update_sync, inspection_id, changes)


async def clear() -> None:
    """Drop every record. Intended for tests."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            _RECORDS.clear()
        return
    await _run("clear the inspections", _clear_sync)


async def check() -> str | None:
    """Probe the store. Returns None when healthy, else a readable reason.

    Used at startup so an unreachable store is reported plainly instead of
    stopping the application from booting.
    """
    if backend() == MEMORY_BACKEND:
        return None

    def _probe() -> None:
        next(iter(_collection().limit(1).stream(timeout=get_settings().store_probe_seconds)), None)

    # A worker thread cannot be interrupted, so the probe is waited on rather
    # than cancelled: startup carries on and the straggler finishes on its own.
    task = asyncio.ensure_future(asyncio.to_thread(_probe))
    done, _pending = await asyncio.wait({task}, timeout=get_settings().store_probe_seconds)
    if not done:
        return "the store did not answer in time"

    error = task.exception()
    if error is None:
        return None
    if isinstance(error, StoreError):
        return str(error)
    return str(_as_store_error(error, "be reached"))
