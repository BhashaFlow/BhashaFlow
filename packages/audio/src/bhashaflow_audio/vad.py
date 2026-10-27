"""Local energy VAD with a trailing-silence end of utterance.

This is the CI and offline path. Muse realtime ``ENDPOINTING`` replaces it
when a live socket is connected: the model emits ``speechEnd`` itself.
Quiet room noise stays under the energy gate. Loud noise can still open a
segment; that is the best-effort limit of an energy detector.
"""

import array
import math
import time

from bhashaflow_audio.budget import END_OF_UTTERANCE_MS, SAMPLE_RATE_HZ, VAD_FRAME_MS
from bhashaflow_audio.pcm import pcm_from_le, pcm_to_le


class VadEvent:
    """Speech onset, or one closed utterance."""

    def __init__(
        self,
        kind: str,
        audio: bytes,
        sample_rate: int,
        latency_ms: float,
        *,
        end_of_utterance: bool,
        silence_ms: int,
    ) -> None:
        self.kind = kind
        self.audio = audio
        self.sample_rate = sample_rate
        self.latency_ms = latency_ms
        self.end_of_utterance = end_of_utterance
        self.silence_ms = silence_ms


class EnergyVad:
    """Open an utterance after a few loud frames and close it after silence."""

    def __init__(
        self,
        *,
        sample_rate: int = SAMPLE_RATE_HZ,
        frame_ms: int = VAD_FRAME_MS,
        silence_ms: int = END_OF_UTTERANCE_MS,
        threshold: float = 800.0,
        start_frames: int = 2,
    ) -> None:
        if sample_rate <= 0 or frame_ms <= 0 or silence_ms <= 0:
            raise ValueError("VAD timings must be positive")
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = sample_rate * frame_ms // 1000
        self.end_frames = max(1, silence_ms // frame_ms)
        self.threshold = threshold
        self.start_frames = start_frames
        self._pending: array.array = array.array("h")
        self._preroll: list[array.array] = []
        self._captured: array.array = array.array("h")
        self._speaking = False
        self._silent_run = 0
        self._noise = 40.0

    def push(self, pcm: bytes, sample_rate: int | None = None) -> list[VadEvent]:
        """Feed PCM. Return speech-start and utterance events."""
        if sample_rate is not None and sample_rate != self.sample_rate:
            raise ValueError("sample rate changed")
        started = time.perf_counter()
        self._pending.extend(pcm_from_le(pcm))
        events: list[VadEvent] = []
        frame = self.frame_samples
        while len(self._pending) >= frame:
            window = self._pending[:frame]
            del self._pending[:frame]
            rms = _rms(window)
            limit = max(self.threshold, self._noise * 3)
            if rms >= limit:
                self._on_voiced(window, events, started)
            else:
                self._on_quiet(rms, events, started)
        return events

    def flush(self) -> list[VadEvent]:
        """Close an open utterance at end of stream."""
        if not self._speaking or len(self._captured) == 0:
            self._speaking = False
            self._captured = array.array("h")
            self._preroll = []
            return []
        audio = pcm_to_le(self._captured)
        self._speaking = False
        self._captured = array.array("h")
        self._silent_run = 0
        self._preroll = []
        return [
            VadEvent(
                "utterance",
                audio,
                self.sample_rate,
                0.0,
                end_of_utterance=True,
                silence_ms=0,
            )
        ]

    def _on_voiced(
        self,
        window: array.array,
        events: list[VadEvent],
        started: float,
    ) -> None:
        self._silent_run = 0
        if self._speaking:
            self._captured.extend(window)
            return
        self._preroll.append(array.array("h", window))
        if len(self._preroll) < self.start_frames:
            return
        self._speaking = True
        for rolled in self._preroll:
            self._captured.extend(rolled)
        self._preroll = []
        events.append(
            VadEvent(
                "speech_start",
                b"",
                self.sample_rate,
                _elapsed_ms(started),
                end_of_utterance=False,
                silence_ms=0,
            )
        )

    def _on_quiet(self, rms: float, events: list[VadEvent], started: float) -> None:
        self._preroll = []
        if not self._speaking:
            if rms < self.threshold:
                self._noise = 0.95 * self._noise + 0.05 * rms
            return
        self._silent_run += 1
        if self._silent_run < self.end_frames:
            return
        audio = pcm_to_le(self._captured)
        silence_ms = self._silent_run * self.frame_ms
        self._speaking = False
        self._captured = array.array("h")
        self._silent_run = 0
        events.append(
            VadEvent(
                "utterance",
                audio,
                self.sample_rate,
                _elapsed_ms(started),
                end_of_utterance=True,
                silence_ms=silence_ms,
            )
        )


def _rms(window: array.array) -> float:
    if not window:
        return 0.0
    total = 0.0
    for sample in window:
        total += float(sample) * float(sample)
    return math.sqrt(total / len(window))


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
