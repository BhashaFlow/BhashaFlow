"""Structured screen and grounding values for the planner and the action engine.

Bounding boxes are pixel coordinates in the frame that produced them, origin at the
top-left. This package does not click or type. The action track maps a grounded
target onto an OS event.
"""

from dataclasses import dataclass
from enum import StrEnum


class GroundingStatus(StrEnum):
    """Whether the vision step produced a target the action engine can use."""

    GROUNDED = "grounded"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned region inside a screen frame."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("bounding box width and height must be positive")
        if self.x < 0 or self.y < 0:
            raise ValueError("bounding box origin must be non-negative")

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def inside(self, width: int, height: int) -> bool:
        return self.x + self.width <= width and self.y + self.height <= height


@dataclass(frozen=True)
class UiElement:
    """One UI element the attention model can name."""

    name: str
    role: str
    bbox: BoundingBox
    accessibility_hint: str
    keywords: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("element name is required")
        if not self.role.strip():
            raise ValueError("element role is required")
        if not self.accessibility_hint.strip():
            raise ValueError("accessibility hint is required")
        if not self.keywords or any(not keyword.strip() for keyword in self.keywords):
            raise ValueError("keywords must be non-empty")


@dataclass(frozen=True)
class ScreenFrame:
    """One desktop frame for the planner.

    ``encoding="rgb"`` means ``pixels`` is raw RGB, ``width * height * 3`` bytes.
    ``encoding="fixture-tag"`` means ``pixels`` is a short scene tag. Fixture
    frames also carry the accessibility snapshot in ``elements``. A pixel model
    should read ``pixels`` and may ignore that snapshot.
    """

    frame_id: int
    width: int
    height: int
    monotonic_ns: int
    scene_id: str
    app: str
    elements: tuple[UiElement, ...]
    pixels: bytes
    encoding: str


@dataclass(frozen=True)
class Candidate:
    """One scored element, included in the overlay debug payload."""

    name: str
    confidence: float


@dataclass(frozen=True)
class GroundingResult:
    """Action-engine handoff for a single intent.

    ``status=low_confidence`` with ``recoverable=True`` is the failure signal
    orchestration uses to retry once. ``target`` is set only when status is
    ``grounded``.
    """

    status: GroundingStatus
    frame_id: int
    target: UiElement | None
    confidence: float
    reason: str
    recoverable: bool
    latency_ms: float
    within_budget: bool

    @property
    def ok(self) -> bool:
        return self.status is GroundingStatus.GROUNDED


@dataclass(frozen=True)
class GroundingEvent:
    """Last grounding decision, including the debug payload the overlay reads."""

    intent: str
    scene_id: str
    app: str
    frame_width: int
    frame_height: int
    result: GroundingResult
    candidates: tuple[Candidate, ...]
