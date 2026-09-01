"""The background job that analyzes an inspection's media."""

import logging
from datetime import datetime, timedelta, timezone

from app.config import get_settings, redact
from app.models.schemas import (
    InspectionResult,
    InspectionStage,
    InspectionStatus,
    SectorDetection,
)
from app.services import analysis_engine, assignment, evidence, inspection_store, storage

logger = logging.getLogger(__name__)

UNDETERMINED_MESSAGE = (
    "The sector could not be determined with confidence from the media. "
    "No audit was run: auditing against the wrong sector's rules would "
    "produce findings that do not apply. Choose the rule set manually "
    "to start the analysis."
)


async def _record_undetermined(
    workspace_id: str, inspection_id: str, detection: SectorDetection
) -> None:
    """Close an inspection whose sector could not be established.

    The media is kept so the auditor can choose a sector without uploading
    again, and only until then: it carries an expiry, and the review screen
    says plainly that it is being held.
    """
    ttl = timedelta(hours=get_settings().undetermined_media_ttl_hours)
    result = InspectionResult(
        inspection_id=inspection_id,
        referentiel="",
        scene_valid=False,
        scene_detected=detection.justification or UNDETERMINED_MESSAGE,
        findings=[],
    )
    await inspection_store.update(
        workspace_id,
        inspection_id,
        status=InspectionStatus.DONE,
        stage=InspectionStage.TERMINE,
        detection=detection.model_dump(mode="json"),
        media_retained=True,
        media_expires_at=(datetime.now(timezone.utc) + ttl).isoformat(),
        result=assignment.enrich(result).model_dump(mode="json"),
        error=None,
    )
    logger.info(
        "Inspection %s left undetermined (confidence %.2f); media held for %.1f h",
        inspection_id, detection.confidence, ttl.total_seconds() / 3600,
    )


async def run_inspection(
    workspace_id: str, inspection_id: str, referentiel: str | None = None
) -> None:
    """Analyze the media held for an inspection and record the outcome.

    Without a rule set the sector is detected first. A sector that cannot
    be established with enough confidence stops the job before any audit: the
    media is retained pending the auditor's choice.

    Any failure is recorded on the inspection rather than raised, so a bad job
    never takes the server down. The media is deleted as soon as an audit runs
    against it, whether that audit succeeds or fails.
    """
    media_path = storage.path(inspection_id)
    audited = False

    try:
        if not referentiel:
            await inspection_store.update(
                workspace_id, inspection_id, stage=InspectionStage.DETECTION
            )
            found = await analysis_engine.detect_sector(media_path)
            threshold = get_settings().detection_min_confidence
            determined = bool(found["referentiel"]) and found["confidence"] >= threshold
            detection = SectorDetection(
                referentiel=found["referentiel"],
                confidence=found["confidence"],
                justification=found["justification"],
                determined=determined,
            )
            if not determined:
                await _record_undetermined(workspace_id, inspection_id, detection)
                return
            referentiel = detection.referentiel
            await inspection_store.update(
                workspace_id, inspection_id, detection=detection.model_dump(mode="json")
            )

        # From here an audit runs, so the media is spent whatever happens.
        audited = True
        await inspection_store.update(workspace_id, inspection_id, stage=InspectionStage.ANALYSE)
        raw = await analysis_engine.analyze(media_path, referentiel)
        result = InspectionResult.model_validate(
            {**raw, "inspection_id": inspection_id, "referentiel": referentiel}
        )
        await inspection_store.update(workspace_id, inspection_id, stage=InspectionStage.ASSIGNATION)
        enriched = assignment.enrich(result)

        try:
            enriched.captured_at = evidence.read_capture_time(media_path)
            evidence.build(inspection_id, media_path, enriched.findings)
        except Exception:  # noqa: BLE001 - evidence is not worth failing over
            logger.exception("Could not build evidence for inspection %s", inspection_id)

        await inspection_store.update(
            workspace_id,
            inspection_id,
            status=InspectionStatus.DONE,
            stage=InspectionStage.TERMINE,
            referentiel=referentiel,
            media_retained=False,
            media_expires_at=None,
            result=enriched.model_dump(mode="json"),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 - the job must never propagate
        logger.exception("Analysis failed for inspection %s", inspection_id)
        await inspection_store.update(
            workspace_id,
            inspection_id,
            status=InspectionStatus.FAILED,
            stage=InspectionStage.TERMINE,
            media_retained=False,
            media_expires_at=None,
            result=None,
            # An exception may quote its input back — a rejected credential
            # included — so what is stored, and later served, is scrubbed.
            error=redact(str(exc)) or exc.__class__.__name__,
        )
    finally:
        # One exit path: any inspection that reached an audit gives up its
        # media, success or failure. Only a sector left undetermined keeps it.
        record = await inspection_store.get(workspace_id, inspection_id)
        keep = bool(record and record.get("media_retained")) and not audited
        if not keep:
            try:
                storage.delete_media(inspection_id)
            except Exception:  # noqa: BLE001 - cleanup must never propagate
                logger.exception("Could not delete media for inspection %s", inspection_id)
