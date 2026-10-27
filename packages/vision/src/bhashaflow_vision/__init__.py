"""Screen-understanding track (Lungile).

Scaffolding only. No capture, models, or screen recording.
"""

from bhashaflow_shared import TRACKS

__version__ = "0.1.0"

TRACK = "vision"


def registered() -> bool:
    return TRACK in TRACKS
