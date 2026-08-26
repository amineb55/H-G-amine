"""The background job that analyzes an inspection's media."""

import logging

from app.models.schemas import InspectionResult, InspectionStatus
from app.services import analysis_engine, assignment, evidence, inspection_store, storage

logger = logging.getLogger(__name__)


async def run_inspection(inspection_id: str, referentiel: str) -> None:
    """Analyze the media held for an inspection and record the outcome.

    Any failure is recorded on the inspection rather than raised, so a bad
    job never takes the server down. The source media is deleted at the end
    either way: only the evidence behind a finding is retained.
    """
    try:
        media_path = storage.path(inspection_id)
        raw = await analysis_engine.analyze(media_path, referentiel)
        result = InspectionResult.model_validate(
            {**raw, "inspection_id": inspection_id, "referentiel": referentiel}
        )
        enriched = assignment.enrich(result)

        # Read the capture time and cut the evidence before the media goes.
        try:
            enriched.captured_at = evidence.read_capture_time(media_path)
            evidence.build(inspection_id, media_path, enriched.findings)
        except Exception:  # noqa: BLE001 - evidence is not worth failing over
            logger.exception("Could not build evidence for inspection %s", inspection_id)

        await inspection_store.update(
            inspection_id,
            status=InspectionStatus.DONE,
            result=enriched.model_dump(mode="json"),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 - the job must never propagate
        logger.exception("Analysis failed for inspection %s", inspection_id)
        await inspection_store.update(
            inspection_id,
            status=InspectionStatus.FAILED,
            result=None,
            error=str(exc) or exc.__class__.__name__,
        )
    finally:
        try:
            storage.delete_media(inspection_id)
        except Exception:  # noqa: BLE001 - cleanup must never propagate
            logger.exception("Could not delete media for inspection %s", inspection_id)
