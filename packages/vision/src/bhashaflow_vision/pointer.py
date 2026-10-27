"""Map a grounded UI element to a click or type target.

The result is data for the action engine. Nothing here moves the pointer,
presses a key, or talks to the OS accessibility API. ``FocusSession`` is the
CI stand-in for window focus: it follows the app on each demo frame.
"""

from bhashaflow_vision.types import BoundingBox, GroundingEvent, GroundingStatus, UiElement

_TYPE_ROLES = frozenset({"textbox", "textfield", "textarea", "searchbox"})


class PointerTarget:
    """Where the action engine would click or type. Not an OS event."""

    def __init__(
        self,
        *,
        action: str,
        x: int,
        y: int,
        bbox: BoundingBox,
        accessibility_id: str,
        app: str,
        element_name: str,
        role: str,
        confidence: float,
        frame_id: int,
    ) -> None:
        self.action = action
        self.x = x
        self.y = y
        self.bbox = bbox
        self.accessibility_id = accessibility_id
        self.app = app
        self.element_name = element_name
        self.role = role
        self.confidence = confidence
        self.frame_id = frame_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PointerTarget):
            return NotImplemented
        return self.__dict__ == other.__dict__


class PointerHandoff:
    """One consume step: a target, or a low-confidence signal with no target."""

    def __init__(
        self,
        *,
        status: GroundingStatus,
        target: PointerTarget | None,
        recoverable: bool,
        reason: str,
        focus_app: str,
        previous_app: str,
        focus_changed: bool,
    ) -> None:
        self.status = status
        self.target = target
        self.recoverable = recoverable
        self.reason = reason
        self.focus_app = focus_app
        self.previous_app = previous_app
        self.focus_changed = focus_changed


def action_kind(role: str) -> str:
    """``type`` for text fields, ``click`` for every other demo role."""
    if role.casefold() in _TYPE_ROLES:
        return "type"
    return "click"


def accessibility_id(app: str, hint: str) -> str:
    """Stable id for one element. Frame ids are not part of it."""
    app_name = app.strip()
    hint_text = hint.strip()
    if app_name:
        return f"{app_name}:{hint_text}"
    return hint_text


def click_point(bbox: BoundingBox) -> tuple[int, int]:
    """Center of the box. Always inside the box for a positive size."""
    return (bbox.x + bbox.width // 2, bbox.y + bbox.height // 2)


def handoff_from_event(event: GroundingEvent, *, previous_app: str = "") -> PointerHandoff:
    """Copy vision's status through. Low confidence never invents a point."""
    current = event.app.strip()
    previous = previous_app.strip()
    changed = bool(previous) and bool(current) and previous != current
    focus_app = current or previous
    result = event.result
    if result.status is not GroundingStatus.GROUNDED or result.target is None:
        return PointerHandoff(
            status=GroundingStatus.LOW_CONFIDENCE,
            target=None,
            recoverable=result.recoverable,
            reason=result.reason or "low confidence",
            focus_app=focus_app,
            previous_app=previous,
            focus_changed=changed,
        )
    target = _target_from_element(result.target, event, result.confidence, result.frame_id)
    return PointerHandoff(
        status=GroundingStatus.GROUNDED,
        target=target,
        recoverable=False,
        reason="",
        focus_app=focus_app,
        previous_app=previous,
        focus_changed=changed,
    )


class FocusSession:
    """Remember the front app across the demo script.

    A desktop build can replace the app string with the OS frontmost app.
    Tests pass the app already stored on each fixture frame.
    """

    def __init__(self) -> None:
        self._previous_app = ""

    def consume(self, event: GroundingEvent) -> PointerHandoff:
        handoff = handoff_from_event(event, previous_app=self._previous_app)
        if event.app.strip():
            self._previous_app = event.app.strip()
        return handoff


def _target_from_element(
    element: UiElement,
    event: GroundingEvent,
    confidence: float,
    frame_id: int,
) -> PointerTarget:
    x, y = click_point(element.bbox)
    return PointerTarget(
        action=action_kind(element.role),
        x=x,
        y=y,
        bbox=element.bbox,
        accessibility_id=accessibility_id(event.app, element.accessibility_hint),
        app=event.app,
        element_name=element.name,
        role=element.role,
        confidence=confidence,
        frame_id=frame_id,
    )
