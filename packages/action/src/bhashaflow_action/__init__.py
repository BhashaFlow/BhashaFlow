"""OS action track (Satinder).

Fixture clicks and typing are the default and do not inject input. Desktop
commands run only when ``BHASHAFLOW_ACTIONS=desktop``, and only for the demo
allowlist.
"""

from bhashaflow_action.allowlist import DEMO_ALLOWLIST
from bhashaflow_action.desktop import DesktopActionEngine, actions_from_env
from bhashaflow_action.engine import DEMO_RECIPIENT, ActionResult, FixtureActionEngine, perform
from bhashaflow_action.targets import FocusSession, PointerHandoff, PointerTarget
from bhashaflow_shared import TRACKS

__version__ = "0.3.0"

TRACK = "action"

__all__ = [
    "DEMO_ALLOWLIST",
    "DEMO_RECIPIENT",
    "TRACK",
    "ActionResult",
    "DesktopActionEngine",
    "FixtureActionEngine",
    "FocusSession",
    "PointerHandoff",
    "PointerTarget",
    "actions_from_env",
    "perform",
    "registered",
]


def registered() -> bool:
    return TRACK in TRACKS
