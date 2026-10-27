"""Stage log. One line per transition so a live miss can be read on the projector."""


class StageLog:
    """Ordered events. ``text`` is the form the CLI prints."""

    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    def event(self, **fields: object) -> None:
        self.entries.append(dict(fields))

    def text(self) -> str:
        lines = []
        for entry in self.entries:
            parts = [f"{key}={_format_field(value)}" for key, value in entry.items()]
            lines.append(" ".join(parts))
        return "\n".join(lines)

    def phases(self) -> list[str]:
        return [str(entry.get("phase", "")) for entry in self.entries]


def _format_field(value: object) -> str:
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    if text == "" or any(char.isspace() for char in text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text
