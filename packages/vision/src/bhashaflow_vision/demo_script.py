"""Fixture scenes for Downloads, then a PDF or a sheet, then mail.

The pixels are tags, not screenshots. Each scene carries the accessibility
snapshot ``FixtureAttention`` scores. Swap in a desktop capture source and an
``AttentionModel`` to run the same session API on a live display.
"""

from bhashaflow_vision.types import BoundingBox, UiElement

FRAME_WIDTH = 1440
FRAME_HEIGHT = 900


class Scene:
    """One app surface in the demo script."""

    def __init__(
        self,
        scene_id: str,
        app: str,
        elements: tuple[UiElement, ...],
        *,
        width: int = FRAME_WIDTH,
        height: int = FRAME_HEIGHT,
    ) -> None:
        self.scene_id = scene_id
        self.app = app
        self.elements = elements
        self.width = width
        self.height = height


def _element(
    name: str,
    role: str,
    box: tuple[int, int, int, int],
    hint: str,
    keywords: tuple[str, ...],
) -> UiElement:
    return UiElement(
        name=name,
        role=role,
        bbox=BoundingBox(*box),
        accessibility_hint=hint,
        keywords=keywords,
    )


def demo_scenes() -> tuple[Scene, ...]:
    """Return the stage script in playback order."""
    downloads = Scene(
        "downloads",
        "Files",
        (
            _element(
                "report.pdf",
                "listitem",
                (48, 160, 320, 40),
                "AXListItem: report.pdf",
                ("report", "pdf"),
            ),
            _element(
                "budget.xlsx",
                "listitem",
                (48, 208, 320, 40),
                "AXListItem: budget.xlsx",
                ("budget", "xlsx", "spreadsheet", "sheet"),
            ),
        ),
    )
    pdf = Scene(
        "pdf",
        "Preview",
        (
            _element(
                "Invoice total",
                "text",
                (860, 420, 180, 36),
                "AXStaticText: Invoice total",
                ("invoice", "total"),
            ),
            _element(
                "Page thumbnail",
                "image",
                (24, 80, 96, 128),
                "AXImage: Page 1",
                ("thumbnail", "page"),
            ),
        ),
    )
    sheet = Scene(
        "sheet",
        "Sheets",
        (
            _element(
                "Total",
                "cell",
                (640, 300, 120, 28),
                "AXCell: Total",
                ("total", "cell"),
            ),
            _element(
                "Date",
                "cell",
                (80, 120, 120, 28),
                "AXCell: Date",
                ("date",),
            ),
        ),
    )
    mail = Scene(
        "mail",
        "Mail",
        (
            _element(
                "Attach",
                "button",
                (980, 860, 120, 36),
                "AXButton: Attach",
                ("attach", "attachment"),
            ),
            _element("To", "textbox", (120, 80, 640, 32), "AXTextField: To", ("recipient",)),
        ),
    )
    return (downloads, pdf, sheet, mail)
