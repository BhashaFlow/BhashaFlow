"""Coordinates vision, audio, and action for one spoken step.

``PlannerLoop`` grounds an utterance and hands the action track a click or
type target. It does not send OS input. Audio is still a placeholder.
"""

from bhashaflow_action import TRACK as ACTION_TRACK
from bhashaflow_audio import TRACK as AUDIO_TRACK
from bhashaflow_orchestrator.loop import PlannerLoop, PlanStep, open_planner
from bhashaflow_shared import TRACKS
from bhashaflow_vision import TRACK as VISION_TRACK

__version__ = "0.2.0"

TRACK = "orchestrator"

__all__ = [
    "TRACK",
    "PlanStep",
    "PlannerLoop",
    "coordinated_tracks",
    "open_planner",
    "registered",
]


def coordinated_tracks() -> tuple[str, ...]:
    """Return the tracks this package is wired to, in demo order."""
    return (VISION_TRACK, AUDIO_TRACK, ACTION_TRACK)


def registered() -> bool:
    wired = set(coordinated_tracks())
    return TRACK in TRACKS and wired <= set(TRACKS)
