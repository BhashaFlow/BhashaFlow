"""Coordinates vision, audio, and action.

``PlannerLoop`` grounds one utterance. ``DemoLoop`` runs the spoken script:
listen, ground, act, confirm, next. The fixture path does not send OS input.
"""

from bhashaflow_action import TRACK as ACTION_TRACK
from bhashaflow_audio import TRACK as AUDIO_TRACK
from bhashaflow_orchestrator.demo import DemoLoop, open_demo
from bhashaflow_orchestrator.loop import PlannerLoop, PlanStep, open_planner
from bhashaflow_shared import TRACKS
from bhashaflow_vision import TRACK as VISION_TRACK

__version__ = "0.3.0"

TRACK = "orchestrator"

__all__ = [
    "TRACK",
    "DemoLoop",
    "PlanStep",
    "PlannerLoop",
    "coordinated_tracks",
    "open_demo",
    "open_planner",
    "registered",
]


def coordinated_tracks() -> tuple[str, ...]:
    """Return the tracks this package is wired to, in demo order."""
    return (VISION_TRACK, AUDIO_TRACK, ACTION_TRACK)


def registered() -> bool:
    wired = set(coordinated_tracks())
    return TRACK in TRACKS and wired <= set(TRACKS)
