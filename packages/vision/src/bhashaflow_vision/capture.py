"""Screen capture sources and the latest-frame buffer the planner polls.

``FixtureCapture`` replays demo scenes and is what CI runs. ``DesktopCapture``
grabs the real display through mss when ``BHASHAFLOW_CAPTURE=desktop``. Probing
and grabbing the desktop are lazy so importing this module never opens a display.
"""

import threading
import time
from typing import Protocol

from bhashaflow_vision.demo_script import Scene
from bhashaflow_vision.types import ScreenFrame, UiElement


class CaptureUnavailable(RuntimeError):
    """The requested capture source cannot produce a frame."""


class FrameSource(Protocol):
    """Something that can grab the next screen frame."""

    def grab(self) -> ScreenFrame:
        """Return the next frame. May raise ``CaptureUnavailable``."""

    def close(self) -> None:
        """Release OS resources. Fixture sources may do nothing."""


class DesktopStatus:
    """Result of asking whether a live desktop can be captured."""

    def __init__(self, available: bool, backend: str, detail: str) -> None:
        self.available = available
        self.backend = backend
        self.detail = detail


class FrameBuffer:
    """Holds the newest frame. Capture overwrites; the planner only reads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: ScreenFrame | None = None

    def publish(self, frame: ScreenFrame) -> None:
        with self._lock:
            self._frame = frame

    def latest(self) -> ScreenFrame | None:
        with self._lock:
            return self._frame


class FixtureCapture:
    """Publish one demo scene until the caller selects another."""

    def __init__(self, scenes: tuple[Scene, ...]) -> None:
        if not scenes:
            raise ValueError("fixture capture needs at least one scene")
        self._scenes = scenes
        self._index = 0
        self._frame_id = 0

    def show(self, scene_id: str) -> None:
        for index, scene in enumerate(self._scenes):
            if scene.scene_id == scene_id:
                self._index = index
                return
        known = ", ".join(scene.scene_id for scene in self._scenes)
        raise KeyError(f"unknown scene {scene_id!r}; known scenes: {known}")

    def grab(self) -> ScreenFrame:
        scene = self._scenes[self._index]
        self._frame_id += 1
        return _frame_from_scene(scene, self._frame_id)

    def close(self) -> None:
        return None


class DesktopCapture:
    """Grab the primary monitor with mss.

    Frames carry RGB pixels and an empty element list. Grounding those frames
    needs an ``AttentionModel`` that reads pixels; the fixture model will report
    low confidence because it only scores ``frame.elements``.
    """

    def __init__(self) -> None:
        self._frame_id = 0

    def grab(self) -> ScreenFrame:
        shot = _grab_primary_monitor()
        self._frame_id += 1
        return ScreenFrame(
            frame_id=self._frame_id,
            width=shot[0],
            height=shot[1],
            monotonic_ns=time.monotonic_ns(),
            scene_id="desktop",
            app="",
            elements=(),
            pixels=shot[2],
            encoding="rgb",
        )

    def close(self) -> None:
        return None


def desktop_capture_status() -> DesktopStatus:
    """Report whether mss can see a primary monitor. Does not raise."""
    try:
        _open_primary_monitor()
    except CaptureUnavailable as exc:
        return DesktopStatus(False, "mss", str(exc))
    return DesktopStatus(True, "mss", "primary monitor available")


def _frame_from_scene(scene: Scene, frame_id: int) -> ScreenFrame:
    elements: tuple[UiElement, ...] = scene.elements
    return ScreenFrame(
        frame_id=frame_id,
        width=scene.width,
        height=scene.height,
        monotonic_ns=time.monotonic_ns(),
        scene_id=scene.scene_id,
        app=scene.app,
        elements=elements,
        pixels=f"fixture:{scene.scene_id}".encode(),
        encoding="fixture-tag",
    )


def _grab_primary_monitor() -> tuple[int, int, bytes]:
    try:
        import mss
    except ImportError as exc:
        raise CaptureUnavailable("desktop capture needs the mss package") from exc
    try:
        with mss.MSS() as sct:
            if len(sct.monitors) < 2:
                raise CaptureUnavailable("no primary monitor reported")
            shot = sct.grab(sct.monitors[1])
            return int(shot.width), int(shot.height), bytes(shot.rgb)
    except CaptureUnavailable:
        raise
    except Exception as exc:
        raise CaptureUnavailable("no desktop is available for screen capture") from exc


def _open_primary_monitor() -> None:
    try:
        import mss
    except ImportError as exc:
        raise CaptureUnavailable("desktop capture needs the mss package") from exc
    try:
        with mss.MSS() as sct:
            if len(sct.monitors) < 2:
                raise CaptureUnavailable("no primary monitor reported")
    except CaptureUnavailable:
        raise
    except Exception as exc:
        raise CaptureUnavailable("no desktop is available for screen capture") from exc
