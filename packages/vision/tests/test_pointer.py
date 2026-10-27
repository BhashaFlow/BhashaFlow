import pytest

from bhashaflow_vision import GroundingStatus
from bhashaflow_vision.pointer import FocusSession, handoff_from_event
from bhashaflow_vision.session import VisionSession
from bhashaflow_vision.types import GroundingEvent, GroundingResult

SURFACES = (
    ("downloads", "open report.pdf in Downloads", "report.pdf", "click", "Files"),
    ("downloads", "open the spreadsheet in Downloads", "budget.xlsx", "click", "Files"),
    ("pdf", "read the invoice total", "Invoice total", "click", "Preview"),
    ("sheet", "select the total cell", "Total", "click", "Sheets"),
    ("mail", "attach the file", "Attach", "click", "Mail"),
    ("mail", "focus the recipient", "To", "type", "Mail"),
)


@pytest.mark.parametrize(("scene", "intent", "name", "kind", "app"), SURFACES)
def test_demo_surfaces_map_to_a_stable_pointer_target(
    scene: str,
    intent: str,
    name: str,
    kind: str,
    app: str,
) -> None:
    session = VisionSession.for_demo_script()
    session.show(scene)
    session.tick()
    first = session.ground(intent)
    session.tick()
    second = session.ground(intent)

    earlier = handoff_from_event(first)
    later = handoff_from_event(second)
    assert earlier.target is not None
    assert later.target is not None
    target = later.target

    assert earlier.status is GroundingStatus.GROUNDED
    assert target.action == kind
    assert target.element_name == name
    assert target.app == app
    assert target.bbox.contains(target.x, target.y)
    assert first.result.target is not None
    assert target.accessibility_id == earlier.target.accessibility_id
    assert target.accessibility_id == f"{app}:{first.result.target.accessibility_hint}"
    assert (target.x, target.y) == (earlier.target.x, earlier.target.y)
    assert target.frame_id != earlier.target.frame_id
    assert target.confidence == first.result.confidence


def test_focus_moves_from_files_through_preview_to_mail() -> None:
    focus = FocusSession()
    apps = _walk(
        focus,
        (
            ("downloads", "open report.pdf in Downloads"),
            ("pdf", "read the invoice total"),
            ("mail", "attach the file"),
        ),
    )
    assert apps == [
        ("Files", "", False),
        ("Preview", "Files", True),
        ("Mail", "Preview", True),
    ]


def test_focus_moves_from_files_to_sheets() -> None:
    focus = FocusSession()
    apps = _walk(
        focus,
        (
            ("downloads", "open the spreadsheet in Downloads"),
            ("sheet", "select the total cell"),
        ),
    )
    assert apps == [
        ("Files", "", False),
        ("Sheets", "Files", True),
    ]


def test_focus_stays_put_for_two_files_in_downloads() -> None:
    focus = FocusSession()
    apps = _walk(
        focus,
        (
            ("downloads", "open report.pdf in Downloads"),
            ("downloads", "open the spreadsheet in Downloads"),
        ),
    )
    assert apps[1] == ("Files", "Files", False)


def test_low_confidence_from_vision_is_recoverable_and_has_no_point() -> None:
    session = VisionSession.for_demo_script()
    session.tick()
    event = session.ground("delete the system partition")
    handoff = FocusSession().consume(event)

    assert event.result.status is GroundingStatus.LOW_CONFIDENCE
    assert handoff.status is GroundingStatus.LOW_CONFIDENCE
    assert handoff.target is None
    assert handoff.recoverable is event.result.recoverable
    assert handoff.recoverable is True
    assert handoff.reason == "low confidence"
    assert handoff.focus_app == "Files"


def test_recoverable_flag_is_copied_when_vision_clears_it() -> None:
    event = _failed_event(recoverable=False, reason="ambiguous", app="Mail")
    handoff = handoff_from_event(event, previous_app="Files")
    assert handoff.target is None
    assert handoff.recoverable is False
    assert handoff.reason == "ambiguous"
    assert handoff.focus_changed is True
    assert handoff.focus_app == "Mail"
    assert handoff.previous_app == "Files"


def _walk(focus: FocusSession, steps: tuple[tuple[str, str], ...]) -> list[tuple[str, str, bool]]:
    session = VisionSession.for_demo_script()
    seen: list[tuple[str, str, bool]] = []
    for scene, intent in steps:
        session.show(scene)
        session.tick()
        handoff = focus.consume(session.ground(intent))
        assert handoff.target is not None
        seen.append((handoff.focus_app, handoff.previous_app, handoff.focus_changed))
    return seen


def _failed_event(*, recoverable: bool, reason: str, app: str) -> GroundingEvent:
    return GroundingEvent(
        intent="unused",
        scene_id="mail",
        app=app,
        frame_width=1440,
        frame_height=900,
        result=GroundingResult(
            status=GroundingStatus.LOW_CONFIDENCE,
            frame_id=1,
            target=None,
            confidence=0.2,
            reason=reason,
            recoverable=recoverable,
            latency_ms=1.0,
            within_budget=True,
        ),
        candidates=(),
    )
