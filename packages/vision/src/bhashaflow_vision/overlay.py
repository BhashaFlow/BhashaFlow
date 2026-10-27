"""Turn ``overlay_payload()`` into draw instructions for the stage overlay.

No window, toolkit, or display is opened. A projector view can replay the
instructions: a high-contrast side panel plus an outline around the selected
element. The panel is placed so it does not cover that element's box, and the
outline is four bars outside the box so the click point stays clear.
"""

import os
from dataclasses import dataclass

from bhashaflow_vision.pointer import action_kind
from bhashaflow_vision.types import BoundingBox

PANEL_COLOR = "#0E1116"
TEXT_COLOR = "#F7F8FA"
ACCENT_COLOR = "#FFD60A"
WARN_COLOR = "#FFB000"
PANEL_WIDTH = 300
SCREEN_MARGIN = 16
OUTLINE = 4
PRIMARY_PX = 36
SECONDARY_PX = 28
_ENV = "BHASHAFLOW_OVERLAY"
_OFF = frozenset({"0", "false", "off", "no"})


@dataclass(frozen=True)
class DrawOp:
    """One rectangle a renderer should fill, stroke, or label."""

    kind: str
    x: int
    y: int
    width: int
    height: int
    color: str
    text: str = ""
    font_px: int = 0

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


@dataclass(frozen=True)
class OverlayScene:
    """Instructions for one grounding step. ``enabled`` is the debug toggle."""

    enabled: bool
    panel: BoundingBox | None
    instructions: tuple[DrawOp, ...]
    target_bbox: BoundingBox | None


class GroundingOverlay:
    """Side panel driven by a vision overlay payload. Toggle hides every op."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def render(self, payload: dict[str, object] | None) -> OverlayScene:
        if not self.enabled or payload is None:
            return OverlayScene(self.enabled, None, (), None)
        frame_w, frame_h = _frame_size(payload)
        target = _target_box(payload)
        status = str(payload.get("status", ""))
        grounded = status == "grounded" and target is not None
        panel = _place_panel(frame_w, frame_h, target if grounded else None)
        ops: list[DrawOp] = [_fill(panel, PANEL_COLOR), _accent(panel)]
        if grounded and target is not None:
            ops.extend(_outline(target))
            name = str(_target_field(payload, "name"))
            role = str(_target_field(payload, "role"))
            lines = (
                (str(payload.get("app", "")), SECONDARY_PX, TEXT_COLOR),
                (name, PRIMARY_PX, ACCENT_COLOR),
                (action_kind(role).upper(), SECONDARY_PX, TEXT_COLOR),
                (str(payload.get("intent", "")), SECONDARY_PX, TEXT_COLOR),
            )
        else:
            reason = str(payload.get("reason") or "low confidence")
            lines = (
                ("LOW CONFIDENCE", PRIMARY_PX, WARN_COLOR),
                (reason, SECONDARY_PX, TEXT_COLOR),
                (
                    "Recoverable" if payload.get("recoverable") else "Not recoverable",
                    SECONDARY_PX,
                    TEXT_COLOR,
                ),
                (str(payload.get("intent", "")), SECONDARY_PX, TEXT_COLOR),
            )
        ops.extend(_labels(panel, lines))
        return OverlayScene(True, panel, tuple(ops), target if grounded else None)


def overlay_from_env() -> GroundingOverlay:
    """``BHASHAFLOW_OVERLAY=0`` starts hidden. Any other value, or unset, shows it."""
    raw = os.environ.get(_ENV, "1").strip().casefold()
    return GroundingOverlay(enabled=raw not in _OFF)


def _frame_size(payload: dict[str, object]) -> tuple[int, int]:
    frame = payload.get("frame")
    if isinstance(frame, dict):
        width = frame.get("width", 0)
        height = frame.get("height", 0)
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return width, height
    return (1440, 900)


def _target_box(payload: dict[str, object]) -> BoundingBox | None:
    target = payload.get("target")
    if not isinstance(target, dict):
        return None
    raw = target.get("bbox")
    if not isinstance(raw, list) or len(raw) != 4 or not all(isinstance(item, int) for item in raw):
        return None
    try:
        return BoundingBox(raw[0], raw[1], raw[2], raw[3])
    except ValueError:
        return None


def _target_field(payload: dict[str, object], key: str) -> object:
    target = payload.get("target")
    if isinstance(target, dict):
        return target.get(key, "")
    return ""


def _place_panel(frame_w: int, frame_h: int, avoid: BoundingBox | None) -> BoundingBox:
    height = max(frame_h - 2 * SCREEN_MARGIN, 1)
    width = min(PANEL_WIDTH, max(frame_w - 2 * SCREEN_MARGIN, 1))
    right_x = max(frame_w - SCREEN_MARGIN - width, 0)
    right = BoundingBox(right_x, min(SCREEN_MARGIN, frame_h - 1), width, height)
    if avoid is None or not _intersects(right, avoid):
        return right
    left = BoundingBox(min(SCREEN_MARGIN, right_x), right.y, width, height)
    if not _intersects(left, avoid):
        return left
    return right


def _intersects(a: BoundingBox, b: BoundingBox) -> bool:
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


def _fill(box: BoundingBox, color: str) -> DrawOp:
    return DrawOp("fill", box.x, box.y, box.width, box.height, color)


def _accent(panel: BoundingBox) -> DrawOp:
    return DrawOp("fill", panel.x, panel.y, panel.width, 8, ACCENT_COLOR)


def _outline(box: BoundingBox) -> tuple[DrawOp, ...]:
    bars = (
        (box.x - OUTLINE, box.y - OUTLINE, box.width + 2 * OUTLINE, OUTLINE),
        (box.x - OUTLINE, box.y + box.height, box.width + 2 * OUTLINE, OUTLINE),
        (box.x - OUTLINE, box.y, OUTLINE, box.height),
        (box.x + box.width, box.y, OUTLINE, box.height),
    )
    ops: list[DrawOp] = []
    for x, y, width, height in bars:
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            continue
        ops.append(DrawOp("stroke", x, y, width, height, ACCENT_COLOR))
    return tuple(ops)


def _labels(
    panel: BoundingBox,
    lines: tuple[tuple[str, int, str], ...],
) -> tuple[DrawOp, ...]:
    pad = 20
    y = panel.y + 24
    width = max(panel.width - 2 * pad, 1)
    ops: list[DrawOp] = []
    for text, font_px, color in lines:
        if not text:
            continue
        ops.append(DrawOp("text", panel.x + pad, y, width, font_px, color, text, font_px))
        y += font_px + 10
    return tuple(ops)
