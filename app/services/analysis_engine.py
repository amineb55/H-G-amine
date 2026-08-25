"""Analysis engine interface.

Vendor-neutral entry point for the AI-assisted analysis. The concrete
provider implementation is injected behind this interface later; for now
the engine returns an empty result.
"""


async def analyze(media_path: str, referentiel: str) -> dict:
    """Analyze a media file against a referential.

    Args:
        media_path: Path to the media file to analyze.
        referentiel: Identifier of the referential to apply.

    Returns:
        A dict matching the ``InspectionResult`` schema.
    """
    return {
        "inspection_id": "",
        "referentiel": referentiel,
        "scene_valid": False,
        "scene_detected": "",
        "findings": [],
    }
