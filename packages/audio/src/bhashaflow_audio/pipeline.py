"""Mic or fixture audio → local VAD → speech-to-text, with barge-in.

``transcriber_from_env`` returns the fixture catalog unless a Model API key
is set. Live Muse is never the default in CI.
"""

import time

from bhashaflow_audio.fixtures import canonical_clips
from bhashaflow_audio.muse import MuseFileTranscriber, Transport, muse_api_key
from bhashaflow_audio.sources import AudioSource, FixtureSource
from bhashaflow_audio.stt import FixtureTranscriber, SpeechToText
from bhashaflow_audio.tts import SpeechSynthesis, StatusSynthesizer
from bhashaflow_audio.types import SpeechSegment
from bhashaflow_audio.vad import EnergyVad


class AudioPipeline:
    """Segment a stream and transcribe each closed utterance."""

    def __init__(
        self,
        stt: SpeechToText,
        tts: SpeechSynthesis | None = None,
        vad: EnergyVad | None = None,
    ) -> None:
        self._stt = stt
        self._tts = StatusSynthesizer() if tts is None else tts
        self._vad = EnergyVad() if vad is None else vad
        self.barge_ins = 0
        self.last_barge_in_ms = 0.0

    def feed(self, pcm: bytes, sample_rate: int) -> list[SpeechSegment]:
        """Push one chunk. Speech onset during a confirmation cancels it."""
        events = self._vad.push(pcm, sample_rate)
        segments: list[SpeechSegment] = []
        for event in events:
            if event.kind == "speech_start" and self._tts.is_speaking():
                started = time.perf_counter()
                self._tts.cancel()
                self.barge_ins += 1
                self.last_barge_in_ms = (time.perf_counter() - started) * 1000
            if event.kind != "utterance":
                continue
            transcript = self._stt.transcribe(event.audio, event.sample_rate)
            segments.append(
                SpeechSegment(
                    transcript=transcript.text,
                    audio=event.audio,
                    sample_rate=event.sample_rate,
                    model=transcript.model,
                    stt_latency_ms=transcript.latency_ms,
                    vad_latency_ms=event.latency_ms,
                    end_of_utterance=event.end_of_utterance,
                    error=transcript.error,
                )
            )
        return segments

    def flush(self) -> list[SpeechSegment]:
        segments: list[SpeechSegment] = []
        for event in self._vad.flush():
            transcript = self._stt.transcribe(event.audio, event.sample_rate)
            segments.append(
                SpeechSegment(
                    transcript=transcript.text,
                    audio=event.audio,
                    sample_rate=event.sample_rate,
                    model=transcript.model,
                    stt_latency_ms=transcript.latency_ms,
                    vad_latency_ms=event.latency_ms,
                    end_of_utterance=event.end_of_utterance,
                    error=transcript.error,
                )
            )
        return segments

    def run(self, source: AudioSource) -> list[SpeechSegment]:
        """Read ``source`` to the end and return every closed utterance with text."""
        segments: list[SpeechSegment] = []
        for pcm, sample_rate in source.chunks():
            segments.extend(self.feed(pcm, sample_rate))
        segments.extend(self.flush())
        return [segment for segment in segments if segment.transcript]


def transcriber_from_env(transport: Transport | None = None) -> SpeechToText:
    """Fixture catalog, or Muse file transcription when a key is set."""
    key = muse_api_key()
    if not key:
        return FixtureTranscriber()
    return MuseFileTranscriber(key, transport=transport)


def transcribe_fixture() -> tuple[str, ...]:
    """Run the canonical script through local VAD and the fixture transcriber."""
    pipeline = AudioPipeline(FixtureTranscriber(), StatusSynthesizer())
    segments = pipeline.run(FixtureSource(canonical_clips()))
    return tuple(segment.transcript for segment in segments)
