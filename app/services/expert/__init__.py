"""The QSE expert's content, loaded as structured, validated data.

Everything under ``docs/expert`` is draft material awaiting the expert's
review. It loads with the status ``pending_validation`` and a watermark, and
must never reach a client-facing path until validated: no module outside this
package reads those files, and no module of the application may import this
package into a serving path (both are enforced by tests).
"""

from app.services.expert.guard import GuardReport, check_exigences
from app.services.expert.loader import (
    PENDING_VALIDATION,
    WATERMARK,
    ExpertBundle,
    ExpertContentError,
    load_bundle,
)

__all__ = [
    "ExpertBundle",
    "ExpertContentError",
    "GuardReport",
    "PENDING_VALIDATION",
    "WATERMARK",
    "check_exigences",
    "load_bundle",
]
