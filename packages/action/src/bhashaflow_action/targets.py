"""Handoff the action engine imports. OS input is not sent from here.

The mapping lives in ``bhashaflow_vision.pointer``. This module is the stable
import for the action track.
"""

from bhashaflow_vision.pointer import (
    FocusSession,
    PointerHandoff,
    PointerTarget,
    action_kind,
    handoff_from_event,
)

__all__ = [
    "FocusSession",
    "PointerHandoff",
    "PointerTarget",
    "action_kind",
    "handoff_from_event",
]
