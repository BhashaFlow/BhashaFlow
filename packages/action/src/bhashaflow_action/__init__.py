"""OS action track (Satinder).

Re-exports the vision pointer handoff. Does not click, type, or inject input.
"""

from bhashaflow_action.targets import FocusSession, PointerHandoff, PointerTarget
from bhashaflow_shared import TRACKS

__version__ = "0.2.0"

TRACK = "action"

__all__ = [
    "TRACK",
    "FocusSession",
    "PointerHandoff",
    "PointerTarget",
    "registered",
]


def registered() -> bool:
    return TRACK in TRACKS
