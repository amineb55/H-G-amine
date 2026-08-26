"""FastAPI application for the HSE inspection analysis service."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse, Response

from app.config import get_settings, redact
from app.models.schemas import (
    DispatchRequest,
    DispatchResponse,
    DispatchStatus,
    FindingEdit,
    FindingSource,
    ManualFinding,
    EnrichedInspectionResult,
    InspectionAccepted,
    InspectionState,
    InspectionStatus,
    Referentiel,
    ReviewResponse,
    ValidationStatus,
)
from app.services import (
    assignment,
    inspection_prompt,
    evidence,
    inspection_store,
    job_queue,
    notification,
    report,
    storage,
)
from app.services.inspection_job import run_inspection
from app.services.notifiers import email_notifier

REVIEW_PAGE = Path(__file__).resolve().parent.parent / "templates" / "review.html"

settings = get_settings()

class RedactingFormatter(logging.Formatter):
    """Scrub configured secret values out of everything that is logged.

    Redacting the message alone is not enough: a traceback rendered from
    ``exc_info`` carries the exception's own text, and a library that rejects
    a malformed header quotes the credential back inside it. Formatting the
    whole record and scrubbing the result covers both.
    """

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


# The server's own logging config leaves the root logger alone, so application
# logs — the store's state, per-call token usage — would never be emitted.
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(levelname)s:     %(name)s - %(message)s",
)
for _handler in logging.getLogger().handlers:
    _handler.setFormatter(RedactingFormatter("%(levelname)s:     %(name)s - %(message)s"))

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Report which backends are active, without blocking startup.

    Nothing here can stop the application coming up: an unreachable backend is
    a loud log line, and every request that needs it says why it failed.
    Secret values are never logged — only the names of the ones missing.
    """
    stripped = settings.stripped_secrets()
    if stripped:
        logger.warning(
            "Surrounding whitespace was stripped from: %s. A value injected "
            "with a trailing newline would otherwise make an HTTP header "
            "illegal. Fix the stored secret to remove the warning.",
            ", ".join(stripped),
        )

    missing = settings.missing_secrets()
    if missing:
        logger.error(
            "Missing configuration: %s. The application is running, but the "
            "features that need them will fail until they are provided.",
            ", ".join(missing),
        )
    else:
        logger.info("Configuration: all required secrets are present.")

    if inspection_store.backend() == inspection_store.MEMORY_BACKEND:
        logger.warning(
            "Inspection store: IN MEMORY. Inspections are lost when this process "
            "stops. Set STORE_BACKEND=firestore to persist them."
        )
    else:
        reason = await inspection_store.check()
        if reason is None:
            logger.info(
                "Inspection store: persistent, collection '%s'.",
                settings.store_collection,
            )
        else:
            logger.error(
                "Inspection store UNREACHABLE: %s. The application is running, "
                "but every inspection request will fail until this is fixed.",
                reason,
            )

    if storage.storage_backend() == storage.LOCAL_BACKEND:
        logger.warning(
            "Evidence storage: LOCAL DISK at '%s'. Evidence is lost when this "
            "instance is replaced. Set STORAGE_BACKEND=gcs to persist it.",
            settings.evidence_dir,
        )
    else:
        reason = await asyncio.to_thread(storage.check_evidence_storage)
        if reason is None:
            logger.info(
                "Evidence storage: object storage, bucket '%s'.",
                settings.evidence_bucket,
            )
        else:
            logger.error(
                "Evidence storage UNREACHABLE: %s. The application is running, "
                "but evidence images will not be stored or served.",
                reason,
            )
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    description="AI-assisted analysis of HSE inspection media.",
    version="0.2.0",
)


@app.exception_handler(inspection_store.StoreError)
async def _store_unavailable(_: Request, exc: inspection_store.StoreError) -> JSONResponse:
    """A store failure is the backend's fault, and the caller is told why."""
    logger.warning("Inspection store failure: %s", exc)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"detail": str(exc)})


@app.exception_handler(storage.StorageError)
async def _storage_unavailable(_: Request, exc: storage.StorageError) -> JSONResponse:
    """Same for evidence storage."""
    logger.warning("Evidence storage failure: %s", exc)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict:
    """Liveness probe.

    Deliberately touches nothing downstream: the platform must not restart a
    healthy container because a database or a bucket is briefly unavailable.
    """
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

    await inspection_store.set(
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
    record = await inspection_store.get(inspection_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown inspection."
        )
    return InspectionState(
        status=record["status"], result=record["result"], error=record["error"]
    )


def _label_for(record: dict, result: EnrichedInspectionResult | None) -> str | None:
    """Human name of the inspection's referential, for display."""
    referentiel = result.referentiel if result else record.get("referentiel")
    return inspection_prompt.referentiel_label(referentiel) if referentiel else None


async def _load_result(inspection_id: str) -> tuple[dict, EnrichedInspectionResult | None]:
    """Return an inspection record and its parsed result."""
    record = await inspection_store.get(inspection_id)
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


async def _set_validation(
    inspection_id: str, index: int, validation_status: ValidationStatus
) -> ReviewResponse:
    """Record a human decision on one finding."""
    record, result = await _load_result(inspection_id)
    result = _require_finding(result, index)

    finding = result.findings[index]
    finding.validation_status = validation_status
    if validation_status is not ValidationStatus.APPROVED:
        # A finding that is no longer approved must not stay queued. What has
        # already been sent stays on the record: it cannot be unsent.
        if finding.dispatch_status is not DispatchStatus.SENT:
            finding.dispatch_status = DispatchStatus.NOT_QUEUED
            finding.dispatch_error = None

    await inspection_store.update(inspection_id, result=result.model_dump(mode="json"))
    return ReviewResponse(
        inspection_id=inspection_id,
        status=record["status"],
        referentiel_label=_label_for(record, result),
        result=result,
        summary=assignment.summarize(result),
        error=record.get("error"),
    )


@app.get("/inspections/{inspection_id}/review", response_model=ReviewResponse)
async def review_inspection(inspection_id: str) -> ReviewResponse:
    """Return the enriched result and the counts the review screen needs."""
    record, result = await _load_result(inspection_id)
    return ReviewResponse(
        inspection_id=inspection_id,
        status=record["status"],
        referentiel_label=_label_for(record, result),
        result=result,
        summary=assignment.summarize(result),
        error=record.get("error"),
    )


@app.post("/inspections/{inspection_id}/findings/{index}/approve", response_model=ReviewResponse)
async def approve_finding(inspection_id: str, index: int) -> ReviewResponse:
    """Approve one finding."""
    return await _set_validation(inspection_id, index, ValidationStatus.APPROVED)


@app.post("/inspections/{inspection_id}/findings/{index}/reject", response_model=ReviewResponse)
async def reject_finding(inspection_id: str, index: int) -> ReviewResponse:
    """Reject one finding."""
    return await _set_validation(inspection_id, index, ValidationStatus.REJECTED)


@app.post("/inspections/{inspection_id}/dispatch", response_model=DispatchResponse)
async def dispatch_inspection(
    inspection_id: str, options: DispatchRequest | None = None
) -> DispatchResponse:
    """Notify the people accountable for the approved findings.

    One email per recipient rather than one per finding, with immediate-stop
    findings pulled into their own message sent first. A finding already sent
    is never sent again, and one failed email never undoes a successful one.
    """
    _, result = await _load_result(inspection_id)
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

    outcomes = await notification.dispatch(result, cc=(options.cc if options else []))

    # Persist whatever happened, successes and failures alike.
    await inspection_store.update(inspection_id, result=result.model_dump(mode="json"))

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


@app.get("/inspections/{inspection_id}/evidence/{filename}", include_in_schema=False)
async def read_evidence(inspection_id: str, filename: str) -> Response:
    """Serve one retained evidence image."""
    if await inspection_store.get(inspection_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown inspection."
        )
    try:
        data = await asyncio.to_thread(storage.get_evidence, inspection_id, filename)
    except storage.StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such evidence image."
        )
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"cache-control": "private, max-age=3600"},
    )


@app.patch("/inspections/{inspection_id}/findings/{index}", response_model=ReviewResponse)
async def edit_finding(inspection_id: str, index: int, edit: FindingEdit) -> ReviewResponse:
    """Apply an auditor's correction to a finding.

    What the analysis originally reported is kept alongside the correction, so
    the change stays auditable, and everything derived from the edited values
    is recomputed.
    """
    record, result = await _load_result(inspection_id)
    result = _require_finding(result, index)
    finding = result.findings[index]

    changes = edit.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to change."
        )

    if "assigned_role" in changes and changes["assigned_role"] not in assignment.known_roles():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role '{changes['assigned_role']}'.",
        )

    # Keep the analysis's own words the first time an auditor overrides them.
    if "observed_severity" in changes and finding.original_severity is None:
        finding.original_severity = finding.observed_severity
    if "observation" in changes and finding.original_observation is None:
        finding.original_observation = finding.observation

    for field, value in changes.items():
        setattr(finding, field, value)
    if finding.source is not FindingSource.HUMAN:
        finding.edited_by_human = True

    assignment.recompute(finding, result.referentiel)
    result.findings = assignment.sort_findings(result.findings)
    await inspection_store.update(inspection_id, result=result.model_dump(mode="json"))

    return ReviewResponse(
        inspection_id=inspection_id, status=record["status"],
        referentiel_label=_label_for(record, result), result=result,
        summary=assignment.summarize(result), error=record.get("error"),
    )


@app.post(
    "/inspections/{inspection_id}/findings",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_finding(inspection_id: str, manual: ManualFinding) -> ReviewResponse:
    """Add a finding the analysis missed."""
    record, result = await _load_result(inspection_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This inspection has no result to add to yet.",
        )

    finding = assignment.build_manual_finding(
        manual.rule_id, manual.observation, manual.observed_severity,
        result.referentiel, timestamp_sec=manual.timestamp_sec,
    )
    result.findings = assignment.sort_findings([*result.findings, finding])
    await inspection_store.update(inspection_id, result=result.model_dump(mode="json"))

    return ReviewResponse(
        inspection_id=inspection_id, status=record["status"],
        referentiel_label=_label_for(record, result), result=result,
        summary=assignment.summarize(result), error=record.get("error"),
    )


@app.get("/inspections/{inspection_id}/report.pdf", include_in_schema=False)
async def read_report(inspection_id: str) -> Response:
    """Generate the inspection's PDF report."""
    _, result = await _load_result(inspection_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This inspection has no result to report on yet.",
        )
    pdf = await asyncio.to_thread(report.build_pdf, result)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "content-disposition": f'inline; filename="{report.report_filename(result)}"'
        },
    )


@app.get("/referentiels/{referentiel}/options", include_in_schema=False)
async def read_options(referentiel: Referentiel) -> dict:
    """Rules and roles the review screen offers when editing a finding."""
    catalog = inspection_prompt.load_catalog(referentiel.value)
    return {
        "rules": [
            {"id": rule.id, "title": rule.title, "default_severity": rule.default_severity.value}
            for rule in catalog.rules
        ],
        "roles": [
            {"key": key, "name": name} for key, name in assignment.known_roles().items()
        ],
    }


@app.get("/debug/notifier", include_in_schema=False)
async def debug_notifier() -> dict:
    """Report what the email notifier can actually reach, step by step.

    Temporary diagnostic tooling for investigating a failure that appears in
    one environment and not another. The response carries no secret: only
    whether one is configured, the host being contacted, and the outcome of
    each step. Remove this endpoint once the problem is understood.
    """
    return await email_notifier.diagnose_connectivity()
