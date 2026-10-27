"""Pluggable speech synthesis.

Muse has no TTS model in the Model API catalog. The demo still needs short
confirmations, so this interface has three backends:

- ``status`` (default): keep the line for the log and the stage indicator.
  Nothing is played and no window is opened.
- ``beep``: write a short local tone to a sink callback. Still no window.
- ``command``: optional non-Muse process, used only when
  ``BHASHAFLOW_TTS_BACKEND=command`` and ``BHASHAFLOW_TTS_COMMAND`` are set.
  CI leaves both unset. The command should be headless; this package does
  not focus a desktop window either way.
"""

import os
import subprocess
import time
from collections.abc import Callable
from typing import Protocol

from bhashaflow_audio.budget import SAMPLE_RATE_HZ
from bhashaflow_audio.pcm import pcm_tone
from bhashaflow_audio.types import SynthesisResult

CommandRunner = Callable[[list[str]], int]
PcmSink = Callable[[bytes], None]


class SpeechSynthesis(Protocol):
    """Speak or record one short confirmation."""

    def speak(self, text: str, *, hold: bool = False) -> SynthesisResult:
        """Play or record ``text``. ``hold`` leaves the backend in the speaking state."""

    def cancel(self) -> None:
        """Stop playback. Used for barge-in."""

    def is_speaking(self) -> bool:
        """Whether a held confirmation is still in progress."""


class StatusSynthesizer:
    """Default confirmation. A log line, not a speaker and not a window."""

    label = "local status (Muse has no TTS)"

    def __init__(self) -> None:
        self._speaking = False
        self.cancelled = False
        self.last_text = ""

    def speak(self, text: str, *, hold: bool = False) -> SynthesisResult:
        started = time.perf_counter()
        self.cancelled = False
        self.last_text = text
        self._speaking = hold
        return SynthesisResult(
            text=text,
            backend="status",
            played=False,
            focus_stolen=False,
            cancelled=False,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    def cancel(self) -> None:
        self._speaking = False
        self.cancelled = True

    def is_speaking(self) -> bool:
        return self._speaking


class BeepSynthesizer:
    """A short local tone. ``sink`` receives PCM and is not a desktop window."""

    label = "local beep (Muse has no TTS)"

    def __init__(self, sink: PcmSink | None = None) -> None:
        self._sink = sink
        self._speaking = False
        self.cancelled = False

    def speak(self, text: str, *, hold: bool = False) -> SynthesisResult:
        started = time.perf_counter()
        self.cancelled = False
        tone = pcm_tone(40, 1200, SAMPLE_RATE_HZ)
        if self._sink is not None:
            self._sink(tone)
        self._speaking = hold
        return SynthesisResult(
            text=text,
            backend="beep",
            played=True,
            focus_stolen=False,
            cancelled=False,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    def cancel(self) -> None:
        self._speaking = False
        self.cancelled = True

    def is_speaking(self) -> bool:
        return self._speaking


class CommandSynthesizer:
    """Optional non-Muse command. Not selected unless the env vars say so."""

    label = "optional non-Muse command"

    def __init__(self, command: str, runner: CommandRunner) -> None:
        self._command = command
        self._runner = runner
        self.cancelled = False
        self._speaking = False

    def speak(self, text: str, *, hold: bool = False) -> SynthesisResult:
        started = time.perf_counter()
        self.cancelled = False
        code = self._runner([self._command, text])
        self._speaking = hold
        return SynthesisResult(
            text=text,
            backend="command",
            played=code == 0,
            focus_stolen=False,
            cancelled=False,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    def cancel(self) -> None:
        self._speaking = False
        self.cancelled = True

    def is_speaking(self) -> bool:
        return self._speaking


def synthesizer_from_env(runner: CommandRunner | None = None) -> SpeechSynthesis:
    """Pick the confirmation backend. Default is local status, with or without a key."""
    backend = os.environ.get("BHASHAFLOW_TTS_BACKEND", "status").strip().casefold() or "status"
    if backend == "beep":
        return BeepSynthesizer()
    if backend == "command":
        command = os.environ.get("BHASHAFLOW_TTS_COMMAND", "").strip()
        if command:
            return CommandSynthesizer(command, _subprocess_runner if runner is None else runner)
    return StatusSynthesizer()


def _subprocess_runner(argv: list[str]) -> int:
    completed = subprocess.run(argv, check=False, capture_output=True)
    return completed.returncode
