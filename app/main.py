"""FastAPI application for the HSE inspection analysis service."""

import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.models.schemas import (
    InspectionAccepted,
    InspectionState,
    InspectionStatus,
    Referentiel,
)
from app.services import inspection_store, job_queue, storage
from app.services.inspection_job import run_inspection

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI-assisted analysis of HSE inspection media.",
    version="0.2.0",
)


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


def _validate_upload(files: list[UploadFile]) -> None:
    """Reject anything that is not one video or a batch of images."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file is required.",
        )

    unsupported = sorted(
        {f.content_type or "unknown" for f in files if f.content_type not in storage.SUPPORTED_MEDIA_TYPES}
    )
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported media type(s): {', '.join(unsupported)}. "
                f"Accepted: {', '.join(sorted(storage.SUPPORTED_MEDIA_TYPES))}."
            ),
        )

    videos = [f for f in files if f.content_type in storage.VIDEO_MEDIA_TYPES]
    images = [f for f in files if f.content_type in storage.IMAGE_MEDIA_TYPES]

    if videos and images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Send either one video or images, not both.",
        )
    if len(videos) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one video can be analyzed per inspection.",
        )
    if len(images) > settings.max_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {settings.max_images} images can be analyzed per inspection.",
        )


@app.post(
    "/inspections",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=InspectionAccepted,
)
async def create_inspection(
    background_tasks: BackgroundTasks,
    referentiel: Referentiel = Form(..., description="Referential to apply."),
    files: list[UploadFile] = File(..., description="One video, or up to ten images."),
) -> InspectionAccepted:
    """Accept inspection media and queue it for AI-assisted analysis."""
    _validate_upload(files)

    inspection_id = str(uuid.uuid4())
    try:
        for upload in files:
            await storage.save(upload, inspection_id)
    except storage.MediaTooLarge as exc:
        storage.delete_media(inspection_id)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except Exception:
        storage.delete_media(inspection_id)
        raise

    inspection_store.set(
        inspection_id,
        {
            "status": InspectionStatus.PROCESSING,
            "referentiel": referentiel.value,
            "result": None,
            "error": None,
        },
    )

    job_queue.get_queue(background_tasks).enqueue(
        run_inspection, inspection_id, referentiel.value
    )

    return InspectionAccepted(
        inspection_id=inspection_id, status=InspectionStatus.PROCESSING
    )


@app.get("/inspections/{inspection_id}", response_model=InspectionState)
async def read_inspection(inspection_id: str) -> InspectionState:
    """Return the current state of an inspection."""
    record = inspection_store.get(inspection_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown inspection."
        )
    return InspectionState(
        status=record["status"], result=record["result"], error=record["error"]
    )
