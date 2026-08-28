"""Analysis engine interface.

Vendor-neutral entry point for the AI-assisted analysis. Callers depend on
this module only; the concrete provider lives under ``providers/`` and is
loaded lazily, so the rest of the application neither imports nor requires
the provider SDK.
"""


async def analyze(media_path: str, referentiel: str) -> dict:
    """Analyze inspection media against a rule set.

    Args:
        media_path: Directory holding the media of one inspection.
        referentiel: Identifier of the rule set to apply.

    Returns:
        A dict matching the ``InspectionResult`` schema.

    Raises:
        Exception: With a readable message when the analysis cannot be done.
    """
    try:
        from app.services.providers import media_provider
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise RuntimeError(
            "The analysis engine provider is not installed. "
            "Install the project dependencies and retry."
        ) from exc

    return await media_provider.analyze(media_path, referentiel)


async def detect_sector(media_path: str) -> dict:
    """Recognise which sector the media shows, before any audit.

    Args:
        media_path: Directory holding the media of one inspection.

    Returns:
        A dict with ``referentiel`` (a known key, or None), ``confidence``
        between 0 and 1, and a short French ``justification``.

    Raises:
        Exception: With a readable message when detection cannot be done.
    """
    try:
        from app.services.providers import media_provider
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise RuntimeError(
            "The analysis engine provider is not installed. "
            "Install the project dependencies and retry."
        ) from exc

    return await media_provider.detect_sector(media_path)
