"""Concrete media analysis provider.

This is the ONLY module allowed to import the provider SDK. Everything above
it talks to ``analysis_engine.analyze()`` and never learns which provider is
in use: the model identifier, the SDK types and the SDK error classes all stop
here, and failures leave as readable ``AnalysisProviderError`` messages.
"""

import asyncio
import json
import logging
import time
from pathlib import Path

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings, redact
from app.models.schemas import Finding, InspectionResult
from app.services import inspection_prompt
from app.services.inspection_prompt import PromptError, build_system_prompt

logger = logging.getLogger(__name__)

# Default model, overridable through ANALYSIS_ENGINE_MODEL. It lives here so
# the provider's identifiers stay inside this module.
DEFAULT_MODEL = "gemini-3.5-flash"

# Media suffixes accepted on disk, mapped to the type sent with the upload.
MEDIA_TYPES: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
VIDEO_TYPES = frozenset({"video/mp4", "video/quicktime"})

UPLOAD_POLL_SECONDS = 2.0
UPLOAD_READY_TIMEOUT_SECONDS = 300.0

CORRECTIVE_INSTRUCTION = (
    "Your previous response could not be parsed against the required schema.\n"
    "Reason: {reason}\n"
    "Return ONLY a JSON object matching the schema exactly. No prose, no code "
    "fences. Use the severity values arret_immediat, critique, majeur or "
    "mineur, the status values nc or a_verifier, and a confidence between 0.0 "
    "and 1.0."
)


class AnalysisProviderError(Exception):
    """A provider failure, already phrased for the person reading it."""


class _AnalysisPayload(BaseModel):
    """What the model is asked to return.

    The inspection id and rule set are known by the caller, so the model is
    not asked to echo them back.
    """

    scene_valid: bool = Field(..., description="Whether the scene matches the rule set.")
    scene_detected: str = Field(..., description="Short description of the scene.")
    findings: list[Finding] = Field(default_factory=list, description="Observed non-conformities.")


def _collect_media(media_dir: str) -> list[Path]:
    """Return the media files held for an inspection, in a stable order."""
    directory = Path(media_dir)
    if not directory.is_dir():
        raise AnalysisProviderError("The inspection media is no longer available.")

    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_TYPES
    )
    if not files:
        raise AnalysisProviderError("No analyzable media was found for this inspection.")
    return files


def _client(api_key: str, timeout_seconds: int) -> genai.Client:
    """Build the SDK client."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
    )


async def _upload(client: genai.Client, path: Path) -> types.File:
    """Upload one media file and wait until it is ready to be analyzed."""
    mime_type = MEDIA_TYPES[path.suffix.lower()]
    uploaded = await client.aio.files.upload(
        file=path, config=types.UploadFileConfig(mime_type=mime_type)
    )

    deadline = time.monotonic() + UPLOAD_READY_TIMEOUT_SECONDS
    while uploaded.state == types.FileState.PROCESSING:
        if time.monotonic() > deadline:
            raise AnalysisProviderError(
                "The analysis engine took too long to prepare the media."
            )
        await asyncio.sleep(UPLOAD_POLL_SECONDS)
        uploaded = await client.aio.files.get(name=uploaded.name)

    if uploaded.state == types.FileState.FAILED:
        raise AnalysisProviderError("The analysis engine could not read the media.")
    return uploaded


def _to_part(uploaded: types.File, sample_fps: float) -> types.Part:
    """Wrap an uploaded file as a request part.

    Video is sampled at a fixed frame rate rather than analyzed frame by
    frame, which is what keeps the cost of a long clip bounded.
    """
    part = types.Part(
        file_data=types.FileData(file_uri=uploaded.uri, mime_type=uploaded.mime_type)
    )
    if uploaded.mime_type in VIDEO_TYPES:
        part.video_metadata = types.VideoMetadata(fps=sample_fps)
    return part


def _log_usage(response: types.GenerateContentResponse, model: str, attempt: int) -> None:
    """Log token usage so the cost of a call can be tracked."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        logger.info("Analysis call: model=%s attempt=%d, no usage reported", model, attempt)
        return
    logger.info(
        "Analysis call: model=%s attempt=%d prompt_tokens=%s output_tokens=%s "
        "thoughts_tokens=%s total_tokens=%s",
        model,
        attempt,
        usage.prompt_token_count,
        usage.candidates_token_count,
        usage.thoughts_token_count,
        usage.total_token_count,
    )


async def _request(
    client: genai.Client,
    model: str,
    system_prompt: str,
    parts: list[types.Part],
    attempt: int,
    correction: str | None = None,
) -> str:
    """Send one request and return the raw response text."""
    request_parts = list(parts)
    if correction is not None:
        request_parts.append(types.Part(text=correction))

    response = await client.aio.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=request_parts)],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=_AnalysisPayload,
            temperature=0.1,
        ),
    )
    _log_usage(response, model, attempt)
    return response.text or ""


def _parse(text: str) -> _AnalysisPayload:
    """Parse and validate one response, raising ValueError when it does not fit."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"response is not valid JSON ({exc})") from exc
    try:
        return _AnalysisPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"response does not match the schema ({exc})") from exc


class _DetectionPayload(BaseModel):
    """What the detection pass returns."""

    referentiel: str | None = Field(None, description="Sector key, or null.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="How sure the pass is.")
    justification: str = Field("", description="What was recognised, in French.")


async def _cleanup(client: genai.Client, uploaded: list[types.File]) -> None:
    """Remove the media copies held by the provider."""
    for item in uploaded:
        try:
            await client.aio.files.delete(name=item.name)
        except Exception:  # noqa: BLE001 - cleanup must never mask the outcome
            logger.warning("Could not delete remote media %s", item.name, exc_info=True)


def _as_readable_error(exc: Exception) -> AnalysisProviderError:
    """Translate an SDK failure into a message worth showing to a person."""
    if isinstance(exc, errors.ClientError):
        code = getattr(exc, "code", None)
        if code == 429:
            return AnalysisProviderError(
                "The analysis engine is rate limited. Retry this inspection later."
            )
        if code in (401, 403):
            return AnalysisProviderError(
                "The analysis engine rejected the configured credentials."
            )
        if code == 400:
            return AnalysisProviderError(
                "The analysis engine rejected the request as invalid."
            )
        return AnalysisProviderError(
            f"The analysis engine rejected the request (status {code})."
        )
    if isinstance(exc, errors.ServerError):
        return AnalysisProviderError(
            "The analysis engine is temporarily unavailable. Retry this inspection later."
        )
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return AnalysisProviderError("The analysis engine did not respond in time.")
    if isinstance(exc, httpx.HTTPError):
        return AnalysisProviderError("The analysis engine could not be reached.")
    return AnalysisProviderError(redact(f"The analysis engine failed: {exc}"))


async def analyze(media_path: str, referentiel: str) -> dict:
    """Analyze the media held in a directory against a rule set.

    Returns a dict matching ``InspectionResult``. Every failure surfaces as an
    ``AnalysisProviderError`` carrying a readable message.
    """
    settings = get_settings()
    api_key = settings.analysis_engine_api_key
    if not api_key:
        raise AnalysisProviderError(
            "The analysis engine is not configured: no API key is set."
        )

    model = settings.analysis_engine_model or DEFAULT_MODEL

    try:
        system_prompt = build_system_prompt(referentiel)
    except PromptError as exc:
        raise AnalysisProviderError(str(exc)) from exc

    files = _collect_media(media_path)
    client = _client(api_key, settings.analysis_engine_timeout_seconds)
    uploaded: list[types.File] = []

    try:
        for path in files:
            uploaded.append(await _upload(client, path))
        parts = [_to_part(item, settings.analysis_engine_video_fps) for item in uploaded]

        text = await _request(client, model, system_prompt, parts, attempt=1)
        try:
            payload = _parse(text)
        except ValueError as first_failure:
            logger.warning("Invalid response, retrying once: %s", first_failure)
            text = await _request(
                client,
                model,
                system_prompt,
                parts,
                attempt=2,
                correction=CORRECTIVE_INSTRUCTION.format(reason=first_failure),
            )
            try:
                payload = _parse(text)
            except ValueError as second_failure:
                logger.error("Invalid response after retry: %s", second_failure)
                raise AnalysisProviderError(
                    "The analysis engine returned a result in an unexpected format, "
                    "twice in a row."
                ) from second_failure
    except AnalysisProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - translated below, never leaked raw
        logger.exception("Analysis request failed")
        raise _as_readable_error(exc) from exc
    finally:
        await _cleanup(client, uploaded)

    result = InspectionResult(
        inspection_id="",
        referentiel=referentiel,
        scene_valid=payload.scene_valid,
        scene_detected=payload.scene_detected,
        findings=payload.findings,
    )
    return result.model_dump(mode="json")


async def detect_sector(media_path: str) -> dict:
    """Recognise the environment shown in the media.

    A deliberately small pass: it carries no rule catalog, asks for three
    short fields, and samples video far more sparsely than the audit does,
    because it only has to place the scene rather than inspect it.

    Returns ``{"referentiel", "confidence", "justification"}``. The caller
    decides what to do with a low score — this function never guesses a
    sector to have something to audit.
    """
    settings = get_settings()
    api_key = settings.analysis_engine_api_key
    if not api_key:
        raise AnalysisProviderError(
            "The analysis engine is not configured: no API key is set."
        )

    model = settings.analysis_engine_model or DEFAULT_MODEL
    try:
        system_prompt = inspection_prompt.build_detection_prompt()
    except PromptError as exc:
        raise AnalysisProviderError(str(exc)) from exc

    files = _collect_media(media_path)
    client = _client(api_key, settings.analysis_engine_timeout_seconds)
    uploaded: list[types.File] = []

    try:
        for path in files:
            uploaded.append(await _upload(client, path))
        parts = [_to_part(item, settings.detection_video_fps) for item in uploaded]

        response = await client.aio.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=_DetectionPayload,
                temperature=0.0,
            ),
        )
        _log_usage(response, model, attempt=0)

        try:
            payload = _DetectionPayload.model_validate(json.loads(response.text or ""))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AnalysisProviderError(
                "The analysis engine could not identify the sector: its answer "
                "was not readable."
            ) from exc
    except AnalysisProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - translated, never leaked raw
        logger.exception("Sector detection failed")
        raise _as_readable_error(exc) from exc
    finally:
        await _cleanup(client, uploaded)

    detected = (payload.referentiel or "").strip().lower() or None
    if detected is not None and detected not in inspection_prompt.supported_referentiels():
        # A sector we do not carry a catalog for is the same as none at all.
        logger.info("Detection returned an unsupported sector: %s", detected)
        detected = None

    logger.info(
        "Sector detection: %s (confidence %.2f)", detected or "none", payload.confidence
    )
    return {
        "referentiel": detected,
        "confidence": payload.confidence,
        "justification": payload.justification.strip(),
    }
