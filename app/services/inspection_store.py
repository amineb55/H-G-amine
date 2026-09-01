"""Persistent state, scoped by workspace at the data layer.

Backed by a document database so records survive a restart, with an
in-memory backend for local work without credentials (``STORE_BACKEND=memory``).
This module is the single database implementation file (P9): tenancy records
and the audit journal go through the generic document functions below rather
than importing a database client of their own.

Tenancy (P8) is enforced HERE, not in the interface: the inspection API
requires a workspace id on every call, every record is stamped with its
workspace, and a read or write naming the wrong workspace behaves exactly as
if the record did not exist. Records stored before multi-tenancy carry no
workspace field and are treated as belonging to the default workspace until
``adopt_unscoped`` stamps them.

The database client is synchronous, so every call runs in a worker thread and
the event loop is never blocked.
"""

import asyncio
import logging
import threading
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

MEMORY_BACKEND = "memory"

# Workspace assumed for records stored before multi-tenancy existed. Kept in
# sync with tenancy.DEFAULT_WORKSPACE_ID (tenancy imports it from here to
# avoid an import cycle with this module).
DEFAULT_WORKSPACE_ID = "ws-default"

_LOCK = threading.Lock()
_TABLES: dict[str, dict[str, dict[str, Any]]] = {}

_client: Any = None
_client_lock = threading.Lock()


class StoreError(Exception):
    """A storage failure, already phrased for the person reading it."""


def backend() -> str:
    """Which backend is in use."""
    return get_settings().store_backend.strip().lower()


def _inspections_collection_name() -> str:
    return get_settings().store_collection


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


def _collection(name: str) -> Any:
    return _get_client().collection(name)


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


def _record_workspace(record: dict[str, Any]) -> str:
    """The workspace a stored record belongs to, pre-tenancy records included."""
    return record.get("workspace_id") or DEFAULT_WORKSPACE_ID


def _memory_table(collection: str) -> dict[str, dict[str, Any]]:
    return _TABLES.setdefault(collection, {})


# --- generic documents: synchronous bodies, each run in a worker thread -----


def _doc_put_sync(collection: str, document_id: str, record: dict[str, Any]) -> dict[str, Any]:
    payload = _encode(record)
    try:
        _collection(collection).document(document_id).set(payload, timeout=_deadline())
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "store this record") from exc
    return dict(payload)


def _doc_get_sync(collection: str, document_id: str) -> dict[str, Any] | None:
    try:
        snapshot = _collection(collection).document(document_id).get(timeout=_deadline())
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "read this record") from exc
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def _doc_merge_sync(
    collection: str, document_id: str, changes: dict[str, Any]
) -> dict[str, Any] | None:
    payload = _encode(changes)
    document = _collection(collection).document(document_id)
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
        raise _as_store_error(exc, "update this record") from exc
    return record


def _doc_add_sync(collection: str, record: dict[str, Any]) -> str:
    payload = _encode(record)
    try:
        _timestamp, reference = _collection(collection).add(payload, timeout=_deadline())
        return reference.id
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "append this record") from exc


def _doc_list_sync(
    collection: str, equals: dict[str, Any] | None
) -> list[tuple[str, dict[str, Any]]]:
    try:
        query: Any = _collection(collection)
        for field_name, value in (equals or {}).items():
            query = query.where(field_name, "==", value)
        return [(doc.id, doc.to_dict() or {}) for doc in query.stream(timeout=_deadline())]
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "list these records") from exc


def _adopt_unscoped_sync(workspace_id: str) -> int:
    """Stamp pre-tenancy inspection records with their workspace."""
    name = _inspections_collection_name()
    adopted = 0
    try:
        for doc in _collection(name).stream(timeout=_deadline()):
            record = doc.to_dict() or {}
            if not record.get("workspace_id"):
                _collection(name).document(doc.id).set(
                    {"workspace_id": workspace_id}, merge=True, timeout=_deadline()
                )
                adopted += 1
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "migrate the unscoped inspections") from exc
    return adopted


def _clear_sync() -> None:
    try:
        client = _get_client()
        for collection in client.collections():
            for document in collection.list_documents(timeout=_deadline()):
                document.delete()
    except StoreError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_store_error(exc, "clear the store") from exc


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


# --- generic document interface (tenancy records, audit journal) ------------


async def put_document(collection: str, document_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Store one document in a named collection, replacing any existing one."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            table = _memory_table(collection)
            table[document_id] = _encode(record)
            return dict(table[document_id])
    return await _run("store this record", _doc_put_sync, collection, document_id, record)


async def get_document(collection: str, document_id: str) -> dict[str, Any] | None:
    """Return one document, or None when it does not exist."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            record = _memory_table(collection).get(document_id)
            return dict(record) if record is not None else None
    return await _run("read this record", _doc_get_sync, collection, document_id)


async def add_document(collection: str, record: dict[str, Any]) -> str:
    """Append one document with a generated id, and return that id."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            document_id = uuid.uuid4().hex
            _memory_table(collection)[document_id] = _encode(record)
            return document_id
    return await _run("append this record", _doc_add_sync, collection, record)


async def list_documents(
    collection: str, equals: dict[str, Any] | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """Documents of a collection, optionally filtered by field equality."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            wanted = _encode(equals or {})
            return [
                (document_id, dict(record))
                for document_id, record in _memory_table(collection).items()
                if all(record.get(field_name) == value for field_name, value in wanted.items())
            ]
    return await _run("list these records", _doc_list_sync, collection, equals)


# --- inspections: workspace-scoped interface --------------------------------


async def set(workspace_id: str, inspection_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Store an inspection in its workspace, replacing any existing one."""
    stamped = {**record, "workspace_id": workspace_id}
    return await put_document(_inspections_collection_name(), inspection_id, stamped)


async def get(workspace_id: str, inspection_id: str) -> dict[str, Any] | None:
    """Return an inspection of this workspace, or None.

    A record belonging to another workspace behaves exactly as if it did not
    exist: tenancy is enforced here, not by the caller.
    """
    record = await get_document(_inspections_collection_name(), inspection_id)
    if record is None or _record_workspace(record) != workspace_id:
        return None
    return record


async def update(
    workspace_id: str, inspection_id: str, **changes: Any
) -> dict[str, Any] | None:
    """Apply changes to an inspection of this workspace, or return None."""
    # The scoped read performs the workspace check; only then is the merge
    # applied. The straggler window between the two is acceptable here: ids
    # are unguessable and both steps name the same record.
    current = await get(workspace_id, inspection_id)
    if current is None:
        return None
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            record = _memory_table(_inspections_collection_name()).get(inspection_id)
            if record is None:
                return None
            record.update(_encode(changes))
            return dict(record)
    return await _run(
        "update this record",
        _doc_merge_sync,
        _inspections_collection_name(),
        inspection_id,
        changes,
    )


async def list_retained() -> list[tuple[str, str, dict[str, Any]]]:
    """Inspections still holding their media, across every workspace.

    Maintenance-only view for the media sweep: it deliberately spans
    workspaces, and returns each record with the workspace it belongs to.
    """
    rows = await list_documents(
        _inspections_collection_name(), {"media_retained": True}
    )
    return [
        (_record_workspace(record), inspection_id, record)
        for inspection_id, record in rows
    ]


async def adopt_unscoped(workspace_id: str) -> int:
    """Stamp pre-tenancy inspections with a workspace. Returns how many."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            adopted = 0
            for record in _memory_table(_inspections_collection_name()).values():
                if not record.get("workspace_id"):
                    record["workspace_id"] = workspace_id
                    adopted += 1
            return adopted
    return await _run("migrate the unscoped inspections", _adopt_unscoped_sync, workspace_id)


async def clear() -> None:
    """Drop every record of every collection. Intended for tests."""
    if backend() == MEMORY_BACKEND:
        with _LOCK:
            _TABLES.clear()
        return
    await _run("clear the store", _clear_sync)


async def check() -> str | None:
    """Probe the store. Returns None when healthy, else a readable reason.

    Used at startup so an unreachable store is reported plainly instead of
    stopping the application from booting.
    """
    if backend() == MEMORY_BACKEND:
        return None

    def _probe() -> None:
        next(
            iter(
                _collection(_inspections_collection_name())
                .limit(1)
                .stream(timeout=get_settings().store_probe_seconds)
            ),
            None,
        )

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
