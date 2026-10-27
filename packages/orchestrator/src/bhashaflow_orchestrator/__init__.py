"""Coordinates the vision, audio, and action tracks (Satinder).

Scaffolding only. No turn loop and no OS control.
"""

from bhashaflow_action import TRACK as ACTION_TRACK
from bhashaflow_audio import TRACK as AUDIO_TRACK
from bhashaflow_shared import TRACKS
from bhashaflow_vision import TRACK as VISION_TRACK

__version__ = "0.1.0"

TRACK = "orchestrator"


def coordinated_tracks() -> tuple[str, ...]:
    """Return the tracks this package is wired to, in demo order."""
    return (VISION_TRACK, AUDIO_TRACK, ACTION_TRACK)


def registered() -> bool:
    wired = set(coordinated_tracks())
    return TRACK in TRACKS and wired <= set(TRACKS)
