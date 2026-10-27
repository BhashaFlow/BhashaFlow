import time

import pytest

from bhashaflow_vision import CAPTURE_INTERVAL_MS, CaptureUnavailable, desktop_capture_status
from bhashaflow_vision.capture import DesktopCapture, FixtureCapture
from bhashaflow_vision.demo_script import demo_scenes
from bhashaflow_vision.session import VisionSession
from bhashaflow_vision.types import ScreenFrame


def test_ticks_publish_the_newest_frame_for_the_planner() -> None:
    session = VisionSession.for_demo_script()
    assert session.latest_frame() is None
    assert session.interval_ms == CAPTURE_INTERVAL_MS

    first = session.tick()
    second = session.tick()
    third = session.tick()

    assert [first.frame_id, second.frame_id, third.frame_id] == [1, 2, 3]
    assert session.latest_frame() == third
    assert third.scene_id == "downloads"
    assert third.encoding == "fixture-tag"
    assert third.pixels == b"fixture:downloads"
    assert third.app == "Files"


def test_background_capture_keeps_publishing_until_stopped() -> None:
    source = _CountingSource()
    session = VisionSession(source, interval_ms=20)
    session.start()
    session.start()

    deadline = time.monotonic() + 2
    while source.grabs < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    session.stop()
    published = source.grabs
    time.sleep(0.08)

    assert published >= 2
    assert source.grabs == published
    assert session.latest_frame() is not None


def test_show_switches_the_fixture_scene() -> None:
    session = VisionSession.for_demo_script()
    session.show("mail")
    frame = session.tick()
    assert frame.scene_id == "mail"
    assert frame.app == "Mail"
    assert {element.name for element in frame.elements} == {"Attach", "To"}


def test_unknown_scene_is_rejected() -> None:
    capture = FixtureCapture(demo_scenes())
    try:
        capture.show("terminal")
    except KeyError as exc:
        assert "terminal" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def test_missing_primary_monitor_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import mss

    class _NoMonitor:
        monitors = [object()]

        def __enter__(self) -> "_NoMonitor":
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(mss, "MSS", _NoMonitor)
    status = desktop_capture_status()
    assert status.available is False
    assert status.backend == "mss"
    assert "monitor" in status.detail.casefold()


def test_desktop_probe_and_grab_agree() -> None:
    status = desktop_capture_status()
    assert status.backend == "mss"
    capture = DesktopCapture()
    if status.available:
        frame = capture.grab()
        assert frame.encoding == "rgb"
        assert frame.elements == ()
        assert frame.scene_id == "desktop"
        assert len(frame.pixels) == frame.width * frame.height * 3
        return
    try:
        capture.grab()
    except CaptureUnavailable as exc:
        assert "desktop" in str(exc).casefold() or "monitor" in str(exc).casefold()
    else:
        raise AssertionError("expected CaptureUnavailable")


def test_desktop_session_cannot_select_a_scene() -> None:
    session = VisionSession(DesktopCapture())
    try:
        session.show("downloads")
    except CaptureUnavailable:
        return
    raise AssertionError("expected CaptureUnavailable")


class _CountingSource:
    def __init__(self) -> None:
        self.grabs = 0

    def grab(self) -> ScreenFrame:
        self.grabs += 1
        return ScreenFrame(
            frame_id=self.grabs,
            width=2,
            height=2,
            monotonic_ns=time.monotonic_ns(),
            scene_id="count",
            app="",
            elements=(),
            pixels=b"rgb",
            encoding="rgb",
        )

    def close(self) -> None:
        return None
