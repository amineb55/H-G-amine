"""Storage for inspection media and for the evidence kept from it.

Uploaded media always lands on local disk: the analysis and the frame
extraction need real files, and it is deleted as soon as the job ends.

Evidence outlives the job, so it goes to object storage — selected by
``STORAGE_BACKEND``, with a local directory for development. Callers never
learn which backend is in use, nor where an object physically lives.
"""

import logging
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.config import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024

# Accepted media types, mapped to the suffix used on disk. Filenames from the
# client are never reused: the suffix is derived from the validated type.
SUPPORTED_MEDIA_TYPES: dict[str, str] = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

VIDEO_MEDIA_TYPES = frozenset({"video/mp4", "video/quicktime"})
IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png"})


# Names allowed for an inspection id or an evidence file.
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageError(Exception):
    """Base class for storage failures."""


class MediaTooLarge(StorageError):
    """Raised when an upload exceeds the per-file size limit."""

    def __init__(self, filename: str, max_bytes: int) -> None:
        self.filename = filename
        self.max_bytes = max_bytes
        super().__init__(f"'{filename}' exceeds the maximum size of {max_bytes} bytes.")


def _root() -> Path:
    """Return the storage root, creating it if needed."""
    root = Path(get_settings().upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve(key: str) -> Path:
    """Resolve a storage key to an absolute path inside the storage root."""
    root = _root()
    target = (root / key).resolve()
    if target != root and root not in target.parents:
        raise StorageError("Invalid storage key.")
    return target


def path(key: str) -> str:
    """Return the absolute path for a storage key."""
    return str(_resolve(key))


async def save(file: UploadFile, inspection_id: str) -> str:
    """Persist an uploaded file and return its storage key.

    The file is streamed in chunks so a large upload is never held in memory,
    and is discarded as soon as it goes over the configured size limit.
    """
    max_bytes = get_settings().max_upload_bytes
    suffix = SUPPORTED_MEDIA_TYPES.get(file.content_type or "", ".bin")
    key = f"{inspection_id}/{uuid.uuid4().hex}{suffix}"

    target = _resolve(key)
    target.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise MediaTooLarge(file.filename or key, max_bytes)
                out.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise

    return key


def delete(key: str) -> None:
    """Delete a stored file or directory. Missing keys are ignored."""
    target = _resolve(key)
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    else:
        target.unlink(missing_ok=True)


def delete_media(inspection_id: str) -> None:
    """Delete every media file held for an inspection.

    Called once the analysis is over, successful or not: only the result is
    retained, never the original media.
    """
    delete(inspection_id)


# --- evidence ---------------------------------------------------------------

GCS_BACKEND = "gcs"
LOCAL_BACKEND = "local"

# Objects are laid out as evidence/{inspection_id}/{filename}.
EVIDENCE_PREFIX = "evidence"

_gcs_bucket: Any = None
_gcs_lock = threading.Lock()


def storage_backend() -> str:
    """Which evidence backend is in use."""
    return get_settings().storage_backend.strip().lower()


def _check_name(inspection_id: str, filename: str) -> None:
    """Refuse anything that could escape an inspection's own space."""
    if not _NAME_PATTERN.match(inspection_id) or not _NAME_PATTERN.match(filename):
        raise StorageError("Invalid evidence name.")


def _object_name(inspection_id: str, filename: str) -> str:
    _check_name(inspection_id, filename)
    return f"{EVIDENCE_PREFIX}/{inspection_id}/{filename}"


def _bucket() -> Any:
    """Return the evidence bucket, built on first use.

    Never called at import: unreachable object storage must not stop the
    application from starting.
    """
    global _gcs_bucket
    if _gcs_bucket is not None:
        return _gcs_bucket
    with _gcs_lock:
        if _gcs_bucket is not None:
            return _gcs_bucket
        name = get_settings().evidence_bucket.strip()
        if not name:
            raise StorageError(
                "Evidence storage is not configured: EVIDENCE_BUCKET is not set."
            )
        try:
            from google.cloud import storage as gcs
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise StorageError(
                "The object storage client is not installed. Install the project "
                "dependencies, or set STORAGE_BACKEND=local."
            ) from exc
        try:
            # No key file: credentials come from the ambient environment.
            _gcs_bucket = gcs.Client().bucket(name)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Could not reach evidence storage: {exc}") from exc
        return _gcs_bucket


def _as_storage_error(exc: Exception, action: str) -> StorageError:
    """Translate a client failure into a message worth showing."""
    name = exc.__class__.__name__
    if name in ("Forbidden", "Unauthorized"):
        return StorageError("Evidence storage rejected the credentials.")
    if name == "NotFound":
        return StorageError("The evidence bucket does not exist.")
    return StorageError(f"Evidence storage could not {action}: {exc}")


def _local_evidence_root() -> Path:
    root = Path(get_settings().evidence_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def put_evidence(inspection_id: str, filename: str, data: bytes) -> None:
    """Store one evidence image."""
    if storage_backend() == LOCAL_BACKEND:
        _check_name(inspection_id, filename)
        directory = _local_evidence_root() / inspection_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(data)
        return
    name = _object_name(inspection_id, filename)
    try:
        _bucket().blob(name).upload_from_string(data, content_type="image/jpeg")
    except StorageError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_storage_error(exc, "store this evidence image") from exc


def get_evidence(inspection_id: str, filename: str) -> bytes | None:
    """Return one evidence image, or None when it is not there."""
    if storage_backend() == LOCAL_BACKEND:
        _check_name(inspection_id, filename)
        target = _local_evidence_root() / inspection_id / filename
        return target.read_bytes() if target.is_file() else None
    name = _object_name(inspection_id, filename)
    try:
        blob = _bucket().blob(name)
        return blob.download_as_bytes() if blob.exists() else None
    except StorageError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_storage_error(exc, "read this evidence image") from exc


def delete_evidence(inspection_id: str) -> None:
    """Remove every evidence image of an inspection."""
    if storage_backend() == LOCAL_BACKEND:
        if not _NAME_PATTERN.match(inspection_id):
            raise StorageError("Invalid evidence name.")
        target = _local_evidence_root() / inspection_id
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        return
    if not _NAME_PATTERN.match(inspection_id):
        raise StorageError("Invalid evidence name.")
    try:
        bucket = _bucket()
        for blob in bucket.list_blobs(prefix=f"{EVIDENCE_PREFIX}/{inspection_id}/"):
            blob.delete()
    except StorageError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_storage_error(exc, "delete this evidence") from exc


def list_evidence(inspection_id: str) -> list[str]:
    """File names of an inspection's evidence, for tests and diagnostics."""
    if storage_backend() == LOCAL_BACKEND:
        target = _local_evidence_root() / inspection_id
        return sorted(p.name for p in target.iterdir()) if target.is_dir() else []
    prefix = f"{EVIDENCE_PREFIX}/{inspection_id}/"
    try:
        return sorted(
            blob.name[len(prefix):] for blob in _bucket().list_blobs(prefix=prefix)
        )
    except StorageError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _as_storage_error(exc, "list this evidence") from exc


def check_evidence_storage() -> str | None:
    """Probe evidence storage. None when healthy, else a readable reason."""
    if storage_backend() == LOCAL_BACKEND:
        return None
    try:
        _bucket().exists()
    except StorageError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return str(_as_storage_error(exc, "be reached"))
    return None
