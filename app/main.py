"""FastAPI application for the HSE inspection analysis service."""

import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models.schemas import (
    DispatchResponse,
    DispatchStatus,
    EnrichedInspectionResult,
    InspectionAccepted,
    InspectionState,
    InspectionStatus,
    Referentiel,
    ReviewResponse,
    ValidationStatus,
)
from app.services import assignment, inspection_store, job_queue, notification, storage
from app.services.inspection_job import run_inspection

REVIEW_PAGE = Path(__file__).resolve().parent.parent / "templates" / "review.html"

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


def _load_result(inspection_id: str) -> tuple[dict, EnrichedInspectionResult | None]:
    """Return an inspection record and its parsed result."""
    record = inspection_store.get(inspection_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown inspection."
        )
    raw = record.get("result")
    result = EnrichedInspectionResult.model_validate(raw) if raw else None
    return record, result


def _require_finding(
    result: EnrichedInspectionResult | None, index: int
) -> EnrichedInspectionResult:
    """Fail unless the result holds a finding at that index."""
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This inspection has no result to review yet.",
        )
    if not 0 <= index < len(result.findings):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"This inspection has no finding at index {index}.",
        )
    return result


def _set_validation(
    inspection_id: str, index: int, validation_status: ValidationStatus
) -> ReviewResponse:
    """Record a human decision on one finding."""
    record, result = _load_result(inspection_id)
    result = _require_finding(result, index)

    finding = result.findings[index]
    finding.validation_status = validation_status
    if validation_status is not ValidationStatus.APPROVED:
        # A finding that is no longer approved must not stay queued. What has
        # already been sent stays on the record: it cannot be unsent.
        if finding.dispatch_status is not DispatchStatus.SENT:
            finding.dispatch_status = DispatchStatus.NOT_QUEUED
            finding.dispatch_error = None

    inspection_store.update(inspection_id, result=result.model_dump(mode="json"))
    return ReviewResponse(
        inspection_id=inspection_id,
        status=record["status"],
        result=result,
        summary=assignment.summarize(result),
        error=record.get("error"),
    )


@app.get("/inspections/{inspection_id}/review", response_model=ReviewResponse)
async def review_inspection(inspection_id: str) -> ReviewResponse:
    """Return the enriched result and the counts the review screen needs."""
    record, result = _load_result(inspection_id)
    return ReviewResponse(
        inspection_id=inspection_id,
        status=record["status"],
        result=result,
        summary=assignment.summarize(result),
        error=record.get("error"),
    )


@app.post("/inspections/{inspection_id}/findings/{index}/approve", response_model=ReviewResponse)
async def approve_finding(inspection_id: str, index: int) -> ReviewResponse:
    """Approve one finding."""
    return _set_validation(inspection_id, index, ValidationStatus.APPROVED)


@app.post("/inspections/{inspection_id}/findings/{index}/reject", response_model=ReviewResponse)
async def reject_finding(inspection_id: str, index: int) -> ReviewResponse:
    """Reject one finding."""
    return _set_validation(inspection_id, index, ValidationStatus.REJECTED)


@app.post("/inspections/{inspection_id}/dispatch", response_model=DispatchResponse)
async def dispatch_inspection(inspection_id: str) -> DispatchResponse:
    """Notify the people accountable for the approved findings.

    One email per recipient rather than one per finding, with immediate-stop
    findings pulled into their own message sent first. A finding already sent
    is never sent again, and one failed email never undoes a successful one.
    """
    _, result = _load_result(inspection_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This inspection has no result to dispatch yet.",
        )

    already_sent: list[int] = []
    unassigned: list[int] = []
    for index, finding in enumerate(result.findings):
        if finding.validation_status is not ValidationStatus.APPROVED:
            continue
        if finding.dispatch_status is DispatchStatus.SENT:
            already_sent.append(index)
        elif not finding.notify_emails:
            unassigned.append(index)

    outcomes = await notification.dispatch(result)

    # Persist whatever happened, successes and failures alike.
    inspection_store.update(inspection_id, result=result.model_dump(mode="json"))

    notified = {i for outcome in outcomes if outcome.status is DispatchStatus.SENT
                for i in outcome.finding_indexes}
    sent_count = sum(1 for o in outcomes if o.status is DispatchStatus.SENT)

    return DispatchResponse(
        inspection_id=inspection_id,
        sent=sent_count > 0,
        emails=outcomes,
        sent_count=sent_count,
        failed_count=len(outcomes) - sent_count,
        already_sent=already_sent,
        approved_from_review=sorted(
            i for i in notified if result.findings[i].requires_review
        ),
        unassigned=unassigned,
    )


@app.get("/review/{inspection_id}", include_in_schema=False)
async def review_page(inspection_id: str) -> FileResponse:
    """Serve the review screen. It loads its data from the review endpoint."""
    if not REVIEW_PAGE.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Review page not available."
        )
    return FileResponse(REVIEW_PAGE, media_type="text/html")
