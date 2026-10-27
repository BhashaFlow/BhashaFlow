"""Stage log. One line per transition so a live miss can be read on the projector."""

import json
import sys
from collections.abc import Callable

from bhashaflow_shared.redact import redact_text

_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40}


class StageLog:
    """Ordered events. ``text`` is the form the CLI prints.

    ``secrets`` are stripped from stored fields and from the optional sink.
    Values shorter than 8 characters are not treated as secrets.
    """

    def __init__(
        self,
        sink: Callable[[dict[str, object]], None] | None = None,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.entries: list[dict[str, object]] = []
        self._sink = sink
        self._secrets = tuple(secret for secret in secrets if len(secret) >= 8)

    def event(self, **fields: object) -> None:
        entry = {key: _redact_field(value, self._secrets) for key, value in fields.items()}
        self.entries.append(entry)
        if self._sink is not None:
            self._sink(entry)

    def text(self) -> str:
        lines = []
        for entry in self.entries:
            parts = [f"{key}={_format_field(value)}" for key, value in entry.items()]
            lines.append(" ".join(parts))
        return "\n".join(lines)

    def phases(self) -> list[str]:
        return [str(entry.get("phase", "")) for entry in self.entries]


def json_stderr_sink(level: str = "info") -> Callable[[dict[str, object]], None]:
    """Write one JSON object per event. ``error`` fields are severity error."""
    threshold = _LEVELS.get(level, _LEVELS["info"])

    def emit(entry: dict[str, object]) -> None:
        severity = "error" if entry.get("error") else "info"
        if _LEVELS[severity] < threshold:
            return
        sys.stderr.write(json.dumps(entry, sort_keys=True) + "\n")

    return emit


def _redact_field(value: object, secrets: tuple[str, ...]) -> object:
    if isinstance(value, str):
        return redact_text(value, secrets)
    return value


def _format_field(value: object) -> str:
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    if text == "" or any(char.isspace() for char in text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text
