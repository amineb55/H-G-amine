"""Evidence kept from an inspection's media.

Only what proves a finding is retained: the source image behind each finding,
or a single still extracted at its timestamp for a video. The originals are
deleted by the job once this has run.
"""

import logging
import re
import subprocess
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import imageio_ffmpeg
from PIL import ExifTags, Image

from app.config import get_settings
from app.services import storage

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
VIDEO_SUFFIXES = frozenset({".mp4", ".mov"})

# EXIF tag holding the moment the shot was taken.
_DATETIME_ORIGINAL = next(
    (tag for tag, name in ExifTags.TAGS.items() if name == "DateTimeOriginal"), None
)
_EXIF_FORMAT = "%Y:%m:%d %H:%M:%S"
_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
_FFPROBE_TIMEOUT = 30
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class EvidenceError(Exception):
    """Raised when evidence cannot be produced."""


def delete_evidence(inspection_id: str) -> None:
    """Remove every evidence image of an inspection."""
    storage.delete_evidence(inspection_id)


def _image_taken_at(path: Path) -> datetime | None:
    """Read EXIF DateTimeOriginal. Returns None when the image carries none."""
    if _DATETIME_ORIGINAL is None:
        return None
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            raw = exif.get(_DATETIME_ORIGINAL)
            if raw is None:
                ifd = exif.get_ifd(ExifTags.IFD.Exif) if hasattr(ExifTags, "IFD") else {}
                raw = ifd.get(_DATETIME_ORIGINAL)
    except Exception:  # noqa: BLE001 - a missing or broken tag is not a failure
        logger.debug("No readable EXIF in %s", path.name, exc_info=True)
        return None
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), _EXIF_FORMAT)
    except ValueError:
        logger.info("Unreadable EXIF capture time in %s: %r", path.name, raw)
        return None


def _video_taken_at(path: Path) -> datetime | None:
    """Read a video's creation time. Returns None when it carries none."""
    try:
        probe = subprocess.run(
            [_FFMPEG, "-i", str(path), "-f", "ffmetadata", "-"],
            capture_output=True, text=True, timeout=_FFPROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        logger.warning("Could not read metadata from %s", path.name, exc_info=True)
        return None

    match = re.search(r"creation_time\s*[:=]\s*(\S+)", probe.stderr + probe.stdout)
    if not match:
        return None
    raw = match.group(1).strip().rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.info("Unreadable creation time in %s: %r", path.name, raw)
    return None


def read_capture_time(media_dir: str) -> datetime | None:
    """When the inspection was shot, or None.

    Taken from the earliest capture time the media carries. Never guessed: a
    file without the metadata contributes nothing.
    """
    directory = Path(media_dir)
    if not directory.is_dir():
        return None

    stamps: list[datetime] = []
    for path in sorted(directory.iterdir()):
        suffix = path.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            stamps.append(_image_taken_at(path))
        elif suffix in VIDEO_SUFFIXES:
            stamps.append(_video_taken_at(path))
    found = [stamp for stamp in stamps if stamp is not None]
    return min(found) if found else None


def _encode_image(source: Path) -> bytes:
    """Read an image, downscaled to a sane size, as JPEG bytes."""
    limit = get_settings().evidence_max_pixels
    buffer = BytesIO()
    with Image.open(source) as image:
        image = image.convert("RGB")
        image.thumbnail((limit, limit))
        image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _extract_frame(video: Path, second: int, destination: Path) -> bool:
    """Extract one still at ``second``. Returns whether it worked."""
    result = subprocess.run(
        [_FFMPEG, "-y", "-ss", str(max(second, 0)), "-i", str(video),
         "-frames:v", "1", "-q:v", "3", str(destination)],
        capture_output=True, text=True, timeout=_FFPROBE_TIMEOUT,
    )
    if result.returncode != 0 or not destination.is_file():
        logger.warning("Could not extract a frame at %ss from %s", second, video.name)
        return False
    return True


def build(inspection_id: str, media_dir: str, findings: list) -> None:
    """Produce the evidence for a set of findings, setting ``evidence_image``.

    Video findings get a still at their timestamp; image findings reference the
    image they came from. Findings whose evidence cannot be produced simply
    keep ``evidence_image`` at None.
    """
    directory = Path(media_dir)
    if not directory.is_dir():
        logger.warning("No media left for inspection %s", inspection_id)
        return

    images = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    videos = sorted(p for p in directory.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES)

    # Frames are cut into a scratch directory, then handed to storage: the
    # backend decides where they actually live.
    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch)

        if videos:
            video = videos[0]
            # One still per distinct timestamp: two findings at the same second
            # share a frame rather than duplicating it.
            for second in sorted({max(int(f.timestamp_sec), 0) for f in findings}):
                name = f"frame-{second:05d}s.jpg"
                cut = workspace / name
                if not _extract_frame(video, second, cut):
                    continue
                try:
                    storage.put_evidence(inspection_id, name, cut.read_bytes())
                except Exception:  # noqa: BLE001 - one lost frame is not a failure
                    logger.warning("Could not store evidence frame %s", name, exc_info=True)
                    continue
                for finding in findings:
                    if max(int(finding.timestamp_sec), 0) == second:
                        finding.evidence_image = name
            return

        if not images:
            return

        # For images the model reports which one it observed, as an index into
        # the batch; anything out of range falls back to the first image.
        kept: dict[int, str] = {}
        for finding in findings:
            position = int(finding.timestamp_sec)
            if not 0 <= position < len(images):
                position = 0
            if position not in kept:
                name = f"image-{position:02d}.jpg"
                try:
                    storage.put_evidence(inspection_id, name, _encode_image(images[position]))
                except Exception:  # noqa: BLE001 - one bad image is not a failure
                    logger.warning("Could not store evidence from %s",
                                   images[position].name, exc_info=True)
                    continue
                kept[position] = name
            finding.evidence_image = kept[position]
