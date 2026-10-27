"""Click, type, focus, and open-app against the demo allowlist.

``FixtureActionEngine`` records what it would do. It does not move the pointer
or inject keys. ``perform`` is the handoff the orchestrator calls.
"""

from bhashaflow_action.allowlist import DEMO_ALLOWLIST
from bhashaflow_vision.pointer import PointerHandoff, PointerTarget

# Typed into the Mail To field when the utterance asks to focus the recipient.
DEMO_RECIPIENT = "demo@bhashaflow.test"
MAX_TYPE_CHARS = 200


class ActionResult:
    """Success or failure for one primitive. ``recoverable`` means try once more."""

    def __init__(
        self,
        *,
        ok: bool,
        action: str,
        app: str,
        detail: str,
        recoverable: bool,
        reason: str,
        target_name: str = "",
    ) -> None:
        self.ok = ok
        self.action = action
        self.app = app
        self.detail = detail
        self.recoverable = recoverable
        self.reason = reason
        self.target_name = target_name


class FixtureActionEngine:
    """In-memory desktop for the stage script. The CI default."""

    def __init__(self, *, fail_once: frozenset[str] = frozenset()) -> None:
        self.front_app = ""
        self.opened: list[str] = []
        self.focused: list[str] = []
        self.clicks: list[str] = []
        self.typed: list[tuple[str, str]] = []
        self._fail_once = fail_once
        self._spent: set[str] = set()

    def open_app(self, app: str) -> ActionResult:
        refused = _refused(app, "open_app")
        if refused is not None:
            return refused
        self.opened.append(app)
        self.front_app = app
        return _ok("open_app", app, app)

    def focus(self, app: str) -> ActionResult:
        refused = _refused(app, "focus")
        if refused is not None:
            return refused
        self.focused.append(app)
        self.front_app = app
        return _ok("focus", app, app)

    def click(self, target: PointerTarget) -> ActionResult:
        refused = _refused(target.app, "click", target.element_name)
        if refused is not None:
            return refused
        missed = self._miss_once(f"click:{target.element_name}", "click", target)
        if missed is not None:
            return missed
        self.clicks.append(target.element_name)
        self.front_app = target.app
        return _ok("click", target.app, target.element_name, target_name=target.element_name)

    def type_text(self, target: PointerTarget, text: str) -> ActionResult:
        refused = _refused(target.app, "type", target.element_name)
        if refused is not None:
            return refused
        rejected = _reject_text(text, target.app, target.element_name)
        if rejected is not None:
            return rejected
        missed = self._miss_once(f"type:{target.element_name}", "type", target)
        if missed is not None:
            return missed
        self.typed.append((target.element_name, text))
        self.front_app = target.app
        return _ok("type", target.app, text, target_name=target.element_name)

    def type_text_raw(self, app: str, element_name: str, text: str) -> ActionResult:
        """Type without a pointer target. Tests use this for rejected text."""
        refused = _refused(app, "type", element_name)
        if refused is not None:
            return refused
        rejected = _reject_text(text, app, element_name)
        if rejected is not None:
            return rejected
        self.typed.append((element_name, text))
        return _ok("type", app, text, target_name=element_name)

    def _miss_once(self, key: str, action: str, target: PointerTarget) -> ActionResult | None:
        if key not in self._fail_once or key in self._spent:
            return None
        self._spent.add(key)
        return ActionResult(
            ok=False,
            action=action,
            app=target.app,
            detail=target.element_name,
            recoverable=True,
            reason=f"{action} missed",
            target_name=target.element_name,
        )


def perform(
    engine: FixtureActionEngine,
    handoff: PointerHandoff,
    *,
    type_text: str,
) -> list[ActionResult]:
    """Open and focus when the front app changes, then click or type.

    A missing target becomes one recoverable or final failure and does not
    call the pointer. The returned list ends with the pointer result.
    """
    target = handoff.target
    if target is None:
        return [
            ActionResult(
                ok=False,
                action="none",
                app=handoff.focus_app,
                detail="",
                recoverable=handoff.recoverable,
                reason=handoff.reason or "no target",
                target_name="",
            )
        ]
    results: list[ActionResult] = []
    front = getattr(engine, "front_app", "")
    if front != target.app:
        opened = engine.open_app(target.app)
        results.append(opened)
        if not opened.ok:
            return results
        focused = engine.focus(target.app)
        results.append(focused)
        if not focused.ok:
            return results
    if target.action == "type":
        results.append(engine.type_text(target, type_text))
    else:
        results.append(engine.click(target))
    return results


def _refused(app: str, action: str, detail: str = "") -> ActionResult | None:
    if app in DEMO_ALLOWLIST:
        return None
    return ActionResult(
        ok=False,
        action=action,
        app=app,
        detail=detail or app,
        recoverable=False,
        reason="app not on demo allowlist",
        target_name=detail,
    )


def _reject_text(text: str, app: str, element_name: str) -> ActionResult | None:
    if not text.strip():
        reason = "nothing to type"
    elif len(text) > MAX_TYPE_CHARS:
        reason = "text too long"
    elif any(ord(char) < 32 for char in text):
        reason = "text rejected"
    else:
        return None
    return ActionResult(
        ok=False,
        action="type",
        app=app,
        detail=text,
        recoverable=False,
        reason=reason,
        target_name=element_name,
    )


def _ok(action: str, app: str, detail: str, *, target_name: str = "") -> ActionResult:
    return ActionResult(
        ok=True,
        action=action,
        app=app,
        detail=detail,
        recoverable=False,
        reason="",
        target_name=target_name,
    )
