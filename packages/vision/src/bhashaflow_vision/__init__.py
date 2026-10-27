"""Screen-understanding track (Lungile).

Publishes near-continuous screen frames and grounds a planner intent onto one
UI element. The default source is a fixture of the demo script. Desktop capture
is a separate adapter and is not used in CI.
"""

from bhashaflow_shared import TRACKS
from bhashaflow_vision.budget import CAPTURE_INTERVAL_MS, GROUND_BUDGET_MS, VISION_STEP_BUDGET_MS
from bhashaflow_vision.capture import CaptureUnavailable, desktop_capture_status
from bhashaflow_vision.overlay import GroundingOverlay, overlay_from_env
from bhashaflow_vision.session import VisionSession, open_session
from bhashaflow_vision.types import GroundingEvent, GroundingResult, GroundingStatus

__version__ = "0.5.0"

TRACK = "vision"

__all__ = [
    "CAPTURE_INTERVAL_MS",
    "GROUND_BUDGET_MS",
    "TRACK",
    "VISION_STEP_BUDGET_MS",
    "CaptureUnavailable",
    "GroundingEvent",
    "GroundingOverlay",
    "GroundingResult",
    "GroundingStatus",
    "VisionSession",
    "desktop_capture_status",
    "open_session",
    "overlay_from_env",
    "registered",
]


def registered() -> bool:
    return TRACK in TRACKS
