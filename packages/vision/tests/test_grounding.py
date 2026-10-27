import json
import time

import pytest

from bhashaflow_vision import GROUND_BUDGET_MS, GroundingStatus, open_session
from bhashaflow_vision.capture import FixtureCapture
from bhashaflow_vision.demo_script import demo_scenes
from bhashaflow_vision.grounding import FixtureAttention, decide
from bhashaflow_vision.session import VisionSession
from bhashaflow_vision.types import ScreenFrame


def test_demo_script_grounds_downloads_pdf_sheet_and_mail() -> None:
    session = VisionSession.for_demo_script()
    steps = (
        ("downloads", "open report.pdf in Downloads", "report.pdf", "AXListItem: report.pdf"),
        ("pdf", "read the invoice total", "Invoice total", "AXStaticText: Invoice total"),
        ("sheet", "select the total cell", "Total", "AXCell: Total"),
        ("mail", "attach the file", "Attach", "AXButton: Attach"),
    )
    for scene_id, intent, name, hint in steps:
        session.show(scene_id)
        frame = session.tick()
        event = session.ground(intent)
        target = event.result.target

        assert event is session.last_event()
        assert event.result.ok
        assert event.result.status is GroundingStatus.GROUNDED
        assert event.result.recoverable is False
        assert target is not None
        assert target.name == name
        assert target.accessibility_hint == hint
        assert target.bbox.inside(frame.width, frame.height)
        assert event.result.confidence >= 0.6
        assert event.result.within_budget
        assert event.result.latency_ms <= GROUND_BUDGET_MS
        assert event.scene_id == scene_id

        payload = session.overlay_payload()
        assert payload is not None
        json.dumps(payload)
        assert payload["status"] == "grounded"
        assert payload["app"] == frame.app
        assert payload["target"]["name"] == name
        assert payload["target"]["bbox"] == list(target.bbox.as_tuple())
        assert payload["target"]["accessibility_hint"] == hint
        assert payload["capture_interval_ms"] == session.interval_ms


def test_spreadsheet_in_downloads_is_a_different_target() -> None:
    session = open_session("fixture")
    session.tick()
    event = session.ground("open the spreadsheet in Downloads")
    assert event.result.ok
    assert event.result.target is not None
    assert event.result.target.name == "budget.xlsx"


def test_low_confidence_is_recoverable_and_has_no_target() -> None:
    session = VisionSession.for_demo_script()
    assert session.overlay_payload() is None

    missing = session.ground("open report.pdf")
    assert missing.result.status is GroundingStatus.LOW_CONFIDENCE
    assert missing.result.reason == "no frame captured"
    assert missing.result.recoverable is True
    assert missing.result.target is None
    assert session.overlay_payload()["recoverable"] is True

    session.tick()
    event = session.ground("delete the system partition")
    assert event.result.status is GroundingStatus.LOW_CONFIDENCE
    assert event.result.reason == "low confidence"
    assert event.result.recoverable is True
    assert event.result.target is None
    assert event.result.confidence == 0.0
    assert session.last_event() is event
    assert session.overlay_payload()["target"] is None
    assert session.overlay_payload()["candidates"]


def test_tied_elements_are_low_confidence() -> None:
    session = VisionSession.for_demo_script()
    session.tick()
    event = session.ground("open report.pdf and budget.xlsx")
    assert event.result.status is GroundingStatus.LOW_CONFIDENCE
    assert event.result.reason == "ambiguous"
    assert event.result.recoverable is True
    assert event.result.target is None
    names = {candidate.name for candidate in event.candidates}
    assert names == {"report.pdf", "budget.xlsx"}


def test_rgb_frame_without_elements_signals_low_confidence() -> None:
    frame = ScreenFrame(
        frame_id=7,
        width=2,
        height=2,
        monotonic_ns=1,
        scene_id="desktop",
        app="",
        elements=(),
        pixels=b"rgb!",
        encoding="rgb",
    )
    result, candidates, _used = decide(frame, "open report.pdf", FixtureAttention())
    assert result.status is GroundingStatus.LOW_CONFIDENCE
    assert result.reason == "no elements on frame"
    assert result.recoverable is True
    assert result.target is None
    assert candidates == ()


def test_slow_model_misses_the_grounding_budget() -> None:
    session = VisionSession(FixtureCapture(demo_scenes()), _SlowModel())
    session.tick()
    event = session.ground("open report.pdf in Downloads")
    assert event.result.within_budget is False
    assert event.result.latency_ms > GROUND_BUDGET_MS


def test_unknown_capture_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="webcam"):
        open_session("webcam")


def test_capture_mode_defaults_to_the_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BHASHAFLOW_CAPTURE", raising=False)
    session = open_session()
    frame = session.tick()
    assert frame.scene_id == "downloads"


class _SlowModel:
    def attend(self, frame: ScreenFrame, intent: str) -> tuple[tuple[object, float], ...]:
        time.sleep(GROUND_BUDGET_MS / 1000 + 0.05)
        return ()
