"""OS action track (Satinder).

Scaffolding only. No keyboard, pointer, or accessibility control.
"""

from bhashaflow_shared import TRACKS

__version__ = "0.1.0"

TRACK = "action"


def registered() -> bool:
    return TRACK in TRACKS
