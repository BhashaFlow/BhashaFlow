"""Process configuration for the fixture rehearsal and the live desktop agent."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_LOG_LEVELS = frozenset({"debug", "info", "warning", "error"})
_LOG_FORMATS = frozenset({"text", "json"})
_ACTIONS = frozenset({"fixture", "desktop"})
_CAPTURES = frozenset({"fixture", "desktop"})
_PLANNERS = frozenset({"fixture", "muse"})
_STT = frozenset({"auto", "file", "realtime", "fixture"})
_TTS = frozenset({"status", "beep", "command"})
_KEY_ENVS = ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY")


class ConfigError(ValueError):
    """A variable is present and not a value this process understands."""


@dataclass(frozen=True)
class AgentConfig:
    """Resolved settings. ``api_key`` is never included in ``repr``."""

    mode: str
    log_level: str
    log_format: str
    actions: str
    capture: str
    planner: str
    stt: str
    tts_backend: str
    tts_command: str
    sam: bool
    muse_timeout_s: float
    muse_retries: int
    api_key: str

    def __repr__(self) -> str:
        state = "set" if self.api_key else "missing"
        return f"AgentConfig(mode={self.mode!r}, api_key={state})"


def parse_config(
    environ: Mapping[str, str] | None = None,
    *,
    mode: str = "fixture",
) -> AgentConfig:
    """Read settings. Empty variables use the mode default. Unknown values raise.

    Live mode defaults to desktop capture, desktop actions, Muse Spark, and
    automatic Muse speech-to-text. Fixture mode keeps the keyless rehearsal.
    """
    if mode not in {"fixture", "live"}:
        raise ConfigError("mode must be fixture or live")
    env = os.environ if environ is None else environ
    live = mode == "live"
    sam_raw = _raw(env, "BHASHAFLOW_SAM")
    if sam_raw in {"", "0"}:
        sam = False
    elif sam_raw == "1":
        sam = True
    else:
        raise ConfigError("BHASHAFLOW_SAM must be 1 or 0")
    return AgentConfig(
        mode=mode,
        log_level=_choice(env, "BHASHAFLOW_LOG_LEVEL", _LOG_LEVELS, "info"),
        log_format=_choice(env, "BHASHAFLOW_LOG_FORMAT", _LOG_FORMATS, "json" if live else "text"),
        actions=_choice(env, "BHASHAFLOW_ACTIONS", _ACTIONS, "desktop" if live else "fixture"),
        capture=_choice(env, "BHASHAFLOW_CAPTURE", _CAPTURES, "desktop" if live else "fixture"),
        planner=_choice(env, "BHASHAFLOW_PLANNER", _PLANNERS, "muse" if live else "fixture"),
        stt=_choice(env, "BHASHAFLOW_STT", _STT, "auto" if live else "fixture"),
        tts_backend=_choice(env, "BHASHAFLOW_TTS_BACKEND", _TTS, "status"),
        tts_command=_raw(env, "BHASHAFLOW_TTS_COMMAND"),
        sam=sam,
        muse_timeout_s=_positive_float(env, "BHASHAFLOW_MUSE_TIMEOUT_S", 8.0),
        muse_retries=_nonnegative_int(env, "BHASHAFLOW_MUSE_RETRIES", 2),
        api_key=_api_key(env),
    )


def load_env_file(path: Path | str, *, override: bool = False) -> list[str]:
    """Load ``KEY=value`` lines. Existing environment variables win unless ``override``.

    The returned list is the names that were set. Values are not returned.
    A missing file is not an error.
    """
    file = Path(path)
    if not file.is_file():
        return []
    loaded: list[str] = []
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if not name or not all(char.isalnum() or char == "_" for char in name):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not override and name in os.environ:
            continue
        os.environ[name] = value
        loaded.append(name)
    return loaded


def _raw(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None:
        return ""
    return value.strip()


def _choice(env: Mapping[str, str], name: str, allowed: frozenset[str], default: str) -> str:
    raw = _raw(env, name)
    if not raw:
        return default
    value = raw.casefold()
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise ConfigError(f"{name} must be one of: {options}")
    return value


def _nonnegative_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _raw(env, name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a non-negative integer") from exc
    if value < 0:
        raise ConfigError(f"{name} must be a non-negative integer")
    return value


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = _raw(env, name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be a positive number")
    return value


def _api_key(env: Mapping[str, str]) -> str:
    for name in _KEY_ENVS:
        value = _raw(env, name)
        if value:
            return value
    return ""
