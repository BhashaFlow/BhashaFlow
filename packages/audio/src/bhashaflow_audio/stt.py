"""Speech-to-text interface. The fixture catalog is the CI default."""

import time
from typing import Protocol

from bhashaflow_audio.fixtures import Clip, canonical_clips
from bhashaflow_audio.types import Transcript


class SpeechToText(Protocol):
    """Transcribe one already-endpointed utterance."""

    def transcribe(self, audio: bytes, sample_rate: int) -> Transcript:
        """Return the text for ``audio``. Empty text is a miss, not a raise."""


class FixtureTranscriber:
    """Map recorded demo clips to their script lines.

    The match is the PCM of the loud portion. VAD strips the trailing silence
    before this is called. Unknown audio becomes an empty transcript so the
    control plane can ignore it.
    """

    model = "fixture"

    def __init__(self, clips: tuple[Clip, ...] | None = None) -> None:
        chosen = canonical_clips() if clips is None else clips
        self._by_audio = {clip.speech: clip.transcript for clip in chosen}

    def transcribe(self, audio: bytes, sample_rate: int) -> Transcript:
        started = time.perf_counter()
        text = self._by_audio.get(audio, "")
        error = "" if text else "no fixture transcript for this audio"
        return Transcript(
            text=text,
            model=self.model,
            latency_ms=(time.perf_counter() - started) * 1000,
            endpointed=True,
            error=error,
        )
