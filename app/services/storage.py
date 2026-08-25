"""Storage abstraction for uploaded inspection media.

Local filesystem implementation. Media for an inspection lives under a
directory named after its ``inspection_id``, so the whole set can be removed
in one call once the analysis is over. A cloud backend can replace the module
body later without changing callers.
"""

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings

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
