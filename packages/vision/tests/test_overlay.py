import pytest

from bhashaflow_vision.overlay import (
    ACCENT_COLOR,
    PANEL_COLOR,
    PRIMARY_PX,
    SECONDARY_PX,
    TEXT_COLOR,
    WARN_COLOR,
    DrawOp,
    GroundingOverlay,
    overlay_from_env,
)
from bhashaflow_vision.session import VisionSession
from bhashaflow_vision.types import BoundingBox

SURFACES = (
    ("downloads", "open report.pdf in Downloads", "report.pdf", "CLICK"),
    ("downloads", "open the spreadsheet in Downloads", "budget.xlsx", "CLICK"),
    ("pdf", "read the invoice total", "Invoice total", "CLICK"),
    ("sheet", "select the total cell", "Total", "CLICK"),
    ("mail", "attach the file", "Attach", "CLICK"),
    ("mail", "focus the recipient", "To", "TYPE"),
)


@pytest.mark.parametrize(("scene", "intent", "name", "kind"), SURFACES)
def test_panel_shows_the_selection_and_leaves_the_click_clear(
    scene: str,
    intent: str,
    name: str,
    kind: str,
) -> None:
    payload = _ground(scene, intent)
    drawn = GroundingOverlay().render(payload)
    target = drawn.target_bbox
    assert target is not None
    assert drawn.panel is not None
    assert not _intersects(drawn.panel, target)

    click_x = target.x + target.width // 2
    click_y = target.y + target.height // 2
    texts = [op for op in drawn.instructions if op.kind == "text"]
    assert any(op.text == name and op.font_px >= PRIMARY_PX for op in texts)
    assert any(op.text == kind and op.font_px >= SECONDARY_PX for op in texts)
    for op in drawn.instructions:
        assert not op.contains(click_x, click_y)
        if op.kind in {"fill", "text"}:
            assert not _intersects(_box(op), target)
        if op.kind == "text":
            assert _contrast(op.color, PANEL_COLOR) >= 7


def test_low_confidence_is_visible_and_draws_no_target() -> None:
    session = VisionSession.for_demo_script()
    session.tick()
    session.ground("delete the system partition")
    payload = session.overlay_payload()
    assert payload is not None
    drawn = GroundingOverlay().render(payload)
    texts = [op.text for op in drawn.instructions if op.kind == "text"]
    assert drawn.target_bbox is None
    assert "LOW CONFIDENCE" in texts
    assert "Recoverable" in texts
    assert not any(op.kind == "stroke" for op in drawn.instructions)


def test_toggle_hides_and_restores_instructions() -> None:
    payload = _ground("mail", "attach the file")
    overlay = GroundingOverlay()
    shown = overlay.render(payload)
    assert shown.enabled is True
    assert shown.instructions

    assert overlay.toggle() is False
    hidden = overlay.render(payload)
    assert hidden.enabled is False
    assert hidden.instructions == ()
    assert hidden.panel is None

    assert overlay.toggle() is True
    assert overlay.render(payload).instructions


def test_right_side_target_moves_the_panel_to_the_left() -> None:
    payload = _ground("downloads", "open report.pdf in Downloads")
    assert isinstance(payload["target"], dict)
    payload["target"]["bbox"] = [1200, 120, 100, 40]
    drawn = GroundingOverlay().render(payload)
    assert drawn.panel is not None
    assert drawn.target_bbox is not None
    assert drawn.panel.x < drawn.target_bbox.x
    assert not _intersects(drawn.panel, drawn.target_bbox)


def test_overlay_env_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BHASHAFLOW_OVERLAY", raising=False)
    assert overlay_from_env().enabled is True
    monkeypatch.setenv("BHASHAFLOW_OVERLAY", "0")
    assert overlay_from_env().enabled is False
    monkeypatch.setenv("BHASHAFLOW_OVERLAY", "off")
    assert overlay_from_env().enabled is False


def test_label_colors_clear_a_projector() -> None:
    assert _contrast(TEXT_COLOR, PANEL_COLOR) >= 7
    assert _contrast(ACCENT_COLOR, PANEL_COLOR) >= 7
    assert _contrast(WARN_COLOR, PANEL_COLOR) >= 7


def _ground(scene: str, intent: str) -> dict[str, object]:
    session = VisionSession.for_demo_script()
    session.show(scene)
    session.tick()
    event = session.ground(intent)
    assert event.result.ok
    payload = session.overlay_payload()
    assert payload is not None
    return payload


def _box(op: DrawOp) -> BoundingBox:
    return BoundingBox(op.x, op.y, op.width, op.height)


def _intersects(a: BoundingBox, b: BoundingBox) -> bool:
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


def _contrast(foreground: str, background: str) -> float:
    darker, lighter = sorted((_luminance(foreground), _luminance(background)))
    return (lighter + 0.05) / (darker + 0.05)


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = []
    for channel in channels:
        if channel <= 0.04045:
            linear.append(channel / 12.92)
        else:
            linear.append(((channel + 0.055) / 1.055) ** 2.4)
    red, green, blue = linear
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue
