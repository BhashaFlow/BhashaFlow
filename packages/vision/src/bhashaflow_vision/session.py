"""Planner-facing vision session: capture loop, grounding, overlay hook."""

import os
import threading

from bhashaflow_vision.budget import CAPTURE_INTERVAL_MS
from bhashaflow_vision.capture import (
    CaptureUnavailable,
    DesktopCapture,
    FixtureCapture,
    FrameBuffer,
    FrameSource,
)
from bhashaflow_vision.demo_script import demo_scenes
from bhashaflow_vision.grounding import AttentionModel, FixtureAttention, decide, event_for
from bhashaflow_vision.types import GroundingEvent, ScreenFrame

_CAPTURE_ENV = "BHASHAFLOW_CAPTURE"


class VisionSession:
    """Near-continuous frames plus the latest grounding event.

    ``start`` captures on a background thread at ``CAPTURE_INTERVAL_MS``.
    ``tick`` performs one grab on the caller thread, which is what tests use.
    ``ground`` always reads the newest buffered frame and does not wait for
    the next grab. ``overlay_payload`` is the hook the stage overlay consumes.
    """

    def __init__(
        self,
        source: FrameSource,
        model: AttentionModel | None = None,
        *,
        interval_ms: int = CAPTURE_INTERVAL_MS,
    ) -> None:
        if interval_ms <= 0:
            raise ValueError("capture interval must be positive")
        self._source = source
        self._model: AttentionModel = FixtureAttention() if model is None else model
        self._interval_ms = interval_ms
        self._buffer = FrameBuffer()
        self._last_event: GroundingEvent | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def for_demo_script(cls, *, interval_ms: int = CAPTURE_INTERVAL_MS) -> "VisionSession":
        return cls(FixtureCapture(demo_scenes()), FixtureAttention(), interval_ms=interval_ms)

    @property
    def interval_ms(self) -> int:
        return self._interval_ms

    def show(self, scene_id: str) -> None:
        """Select a fixture scene. Desktop capture has no scenes."""
        show = getattr(self._source, "show", None)
        if show is None:
            raise CaptureUnavailable("this capture source has no scenes to select")
        show(scene_id)

    def tick(self) -> ScreenFrame:
        """Grab once and publish the frame for the planner."""
        frame = self._source.grab()
        self._buffer.publish(frame)
        return frame

    def latest_frame(self) -> ScreenFrame | None:
        return self._buffer.latest()

    def start(self) -> None:
        """Capture until ``stop``. A second call while running does nothing."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="bhashaflow-vision-capture",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._stop.set()
        thread.join(timeout=2)
        if thread.is_alive():
            raise RuntimeError("capture loop did not stop")
        self._thread = None

    def ground(self, intent: str) -> GroundingEvent:
        """Name the UI element for ``intent``, or signal low confidence."""
        result, candidates, frame = decide(self.latest_frame(), intent, self._model)
        event = event_for(intent, result, frame, candidates)
        with self._lock:
            self._last_event = event
        return event

    def last_event(self) -> GroundingEvent | None:
        with self._lock:
            return self._last_event

    def overlay_payload(self) -> dict[str, object] | None:
        """JSON-ready debug payload for the stage overlay.

        Returns ``None`` before the first ``ground`` call. Bounding boxes are
        ``[x, y, width, height]`` in the frame that was scored.
        """
        event = self.last_event()
        if event is None:
            return None
        target = event.result.target
        target_payload: dict[str, object] | None
        if target is None:
            target_payload = None
        else:
            target_payload = {
                "name": target.name,
                "role": target.role,
                "bbox": list(target.bbox.as_tuple()),
                "accessibility_hint": target.accessibility_hint,
            }
        return {
            "status": event.result.status.value,
            "intent": event.intent,
            "scene_id": event.scene_id,
            "app": event.app,
            "frame_id": event.result.frame_id,
            "confidence": event.result.confidence,
            "recoverable": event.result.recoverable,
            "reason": event.result.reason,
            "latency_ms": event.result.latency_ms,
            "within_budget": event.result.within_budget,
            "capture_interval_ms": self._interval_ms,
            "target": target_payload,
            "frame": {"width": event.frame_width, "height": event.frame_height},
            "candidates": [
                {"name": candidate.name, "confidence": candidate.confidence}
                for candidate in event.candidates
            ],
        }

    def close(self) -> None:
        self.stop()
        self._source.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self._interval_ms / 1000)


def open_session(mode: str | None = None) -> VisionSession:
    """Open a session from ``mode`` or ``BHASHAFLOW_CAPTURE``.

    ``fixture`` (the default) replays the demo script. ``desktop`` grabs the
    primary monitor and still uses fixture attention until a pixel model is
    supplied, so grounding a live frame with no elements returns low confidence.
    """
    selected = mode if mode is not None else os.environ.get(_CAPTURE_ENV, "fixture")
    selected = selected.strip().casefold()
    if selected == "fixture":
        return VisionSession.for_demo_script()
    if selected == "desktop":
        return VisionSession(DesktopCapture(), FixtureAttention())
    raise ValueError(f"unknown capture mode {selected!r}; use 'fixture' or 'desktop'")
