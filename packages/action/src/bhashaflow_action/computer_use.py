"""Optional long-horizon computer use on Muse Wonder.

The Meta computer-use guide runs this loop on ``muse-wonder-1.0`` through
``POST /v1/responses`` and the ``computer`` tool. That is not the tight demo
loop. Per-utterance grounding stays on the fixture planner, or on
``muse-spark-1.3`` when that opt-in is selected.

This module builds one request and reads one ``computer_call``. It does not
acknowledge safety checks. Pending checks are a hard stop. Actions are not
executed unless the front app is on the demo allowlist.
"""

from bhashaflow_action.allowlist import DEMO_ALLOWLIST
from bhashaflow_action.engine import ActionResult

WONDER_MODEL = "muse-wonder-1.0"
SPARK_TIGHT_LOOP_MODEL = "muse-spark-1.3"
WONDER_URL = "https://api.meta.ai/v1/responses"


class ComputerAction:
    """One action inside a computer_call batch."""

    def __init__(self, kind: str, fields: dict[str, object]) -> None:
        self.kind = kind
        self.fields = fields


class ComputerCall:
    """The model's batch, plus any safety checks the caller must review."""

    def __init__(
        self,
        call_id: str,
        actions: tuple[ComputerAction, ...],
        safety_checks: tuple[dict[str, object], ...],
    ) -> None:
        self.call_id = call_id
        self.actions = actions
        self.safety_checks = safety_checks


def wonder_request(task: str, screenshot_data_url: str) -> dict[str, object]:
    """One Responses API turn. The model is Wonder, as the computer-use guide specifies."""
    return {
        "model": WONDER_MODEL,
        "tools": [{"type": "computer"}],
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": task},
                    {"type": "input_image", "image_url": screenshot_data_url},
                ],
            }
        ],
    }


def parse_computer_call(response: dict[str, object]) -> ComputerCall | None:
    """Return the first computer_call, or None when the model finished without one."""
    output = response.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "computer_call":
            continue
        raw_actions = item.get("actions")
        actions: list[ComputerAction] = []
        if isinstance(raw_actions, list):
            for action in raw_actions:
                if isinstance(action, dict) and isinstance(action.get("type"), str):
                    actions.append(ComputerAction(str(action["type"]), dict(action)))
        checks = item.get("pending_safety_checks")
        safety: list[dict[str, object]] = []
        if isinstance(checks, list):
            safety.extend(check for check in checks if isinstance(check, dict))
        call_id = item.get("call_id")
        return ComputerCall(
            "" if not isinstance(call_id, str) else call_id,
            tuple(actions),
            tuple(safety),
        )
    return None


def gate_computer_call(call: ComputerCall, front_app: str) -> ActionResult | None:
    """Refuse the batch when the app is off-list or a safety check is pending.

    Returns None when the caller may execute the batch through the allowlisted
    engine. This function never acknowledges a safety check.
    """
    if front_app not in DEMO_ALLOWLIST:
        return ActionResult(
            ok=False,
            action="computer_use",
            app=front_app,
            detail=call.call_id,
            recoverable=False,
            reason="app not on demo allowlist",
        )
    if call.safety_checks:
        return ActionResult(
            ok=False,
            action="computer_use",
            app=front_app,
            detail=call.call_id,
            recoverable=False,
            reason="safety check pending",
        )
    return None
