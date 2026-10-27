"""Mic → VAD → STT, plus a TTS interface that does not steal focus.

CI never calls Meta. Live Muse runs only when a transport is injected or a
key is present and the caller builds ``MuseFileTranscriber`` itself.
"""

import pytest

from bhashaflow_audio.budget import (
    BARGE_IN_BUDGET_MS,
    END_OF_UTTERANCE_MS,
    FIXTURE_STT_BUDGET_MS,
    MUSE_STT_ESTIMATE_MS,
    SAMPLE_RATE_HZ,
    TTS_CONFIRM_BUDGET_MS,
    VAD_DECISION_BUDGET_MS,
)
from bhashaflow_audio.fixtures import CANONICAL_UTTERANCES, canonical_clips, make_clip, noise_clip
from bhashaflow_audio.muse import (
    MUSE_ASR_MODEL,
    MUSE_REALTIME_URL,
    MuseFileTranscriber,
    MuseRealtimeSession,
)
from bhashaflow_audio.pipeline import AudioPipeline, transcribe_fixture, transcriber_from_env
from bhashaflow_audio.sources import FixtureSource, MicrophoneSource
from bhashaflow_audio.tts import StatusSynthesizer, synthesizer_from_env
from bhashaflow_audio.vad import EnergyVad


def test_trailing_silence_closes_one_utterance() -> None:
    vad = EnergyVad()
    clip = make_clip("open report.pdf in Downloads")
    started = vad.push(clip.speech, SAMPLE_RATE_HZ)
    assert [event.kind for event in started] == ["speech_start"]
    closed = vad.push(clip.silence, SAMPLE_RATE_HZ)
    assert [event.kind for event in closed] == ["utterance"]
    assert closed[0].audio == clip.speech
    assert closed[0].end_of_utterance is True
    assert closed[0].silence_ms >= END_OF_UTTERANCE_MS
    assert closed[0].latency_ms <= VAD_DECISION_BUDGET_MS


def test_quiet_ambient_noise_does_not_open_an_utterance() -> None:
    vad = EnergyVad()
    events = vad.push(noise_clip(duration_ms=1000, amplitude=80), SAMPLE_RATE_HZ)
    assert events == []
    assert vad.flush() == []


def test_fixture_demo_lines_need_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    heard = transcribe_fixture()
    assert heard == CANONICAL_UTTERANCES
    assert heard[0] == "open report.pdf in Downloads"
    assert "report.pdf" in heard[0]
    pipeline = AudioPipeline(transcriber_from_env(), synthesizer_from_env())
    segments = pipeline.run(FixtureSource(canonical_clips()))
    assert [segment.transcript for segment in segments] == list(CANONICAL_UTTERANCES)
    assert all(segment.end_of_utterance for segment in segments)
    assert all(segment.stt_latency_ms <= FIXTURE_STT_BUDGET_MS for segment in segments)
    assert all(segment.model == "fixture" for segment in segments)


def test_microphone_frames_use_the_same_vad_and_stt_path(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    clip = canonical_clips()[0]
    frames = [clip.speech, clip.silence]

    def reader() -> bytes:
        if frames:
            return frames.pop(0)
        return b""

    segments = AudioPipeline(transcriber_from_env(), StatusSynthesizer()).run(
        MicrophoneSource(reader, sample_rate=SAMPLE_RATE_HZ)
    )
    assert segments[0].transcript == "open report.pdf in Downloads"
    assert segments[0].end_of_utterance is True


def test_barge_in_cancels_a_confirmation_without_stealing_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    tts = StatusSynthesizer()
    pipeline = AudioPipeline(transcriber_from_env(), tts)
    spoken = tts.speak("Clicked report.pdf", hold=True)
    assert spoken.focus_stolen is False
    assert spoken.backend == "status"
    assert spoken.latency_ms <= TTS_CONFIRM_BUDGET_MS
    assert tts.is_speaking()
    clip = canonical_clips()[0]
    started = pipeline.feed(clip.speech, SAMPLE_RATE_HZ)
    assert started == []
    assert tts.is_speaking() is False
    assert tts.cancelled is True
    assert pipeline.barge_ins == 1
    assert pipeline.last_barge_in_ms <= BARGE_IN_BUDGET_MS
    closed = pipeline.feed(clip.silence, SAMPLE_RATE_HZ)
    assert closed[0].transcript == "open report.pdf in Downloads"


def test_default_tts_is_local_status_and_command_backend_is_labeled_non_muse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("BHASHAFLOW_TTS_BACKEND", "BHASHAFLOW_TTS_COMMAND"):
        monkeypatch.delenv(name, raising=False)
    default = synthesizer_from_env()
    assert isinstance(default, StatusSynthesizer)
    result = default.speak("Listening")
    assert result.played is False
    assert result.focus_stolen is False
    assert "muse" not in result.backend

    monkeypatch.setenv("BHASHAFLOW_TTS_BACKEND", "command")
    monkeypatch.setenv("BHASHAFLOW_TTS_COMMAND", "true")
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    command = synthesizer_from_env(runner=runner)
    spoken = command.speak("Listening")
    assert spoken.backend == "command"
    assert spoken.focus_stolen is False
    assert spoken.played is True
    assert calls == [["true", "Listening"]]
    assert "non-Muse" in command.label


def test_muse_file_transcribe_posts_the_voice_model() -> None:
    captured: dict[str, object] = {}

    def transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["body"] = body
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "sessionId": "fixture-session",
            "transcript": "open report.pdf in Downloads",
            "audioDurationMs": 200,
            "turns": [
                {
                    "turnId": 1,
                    "startMs": 0,
                    "endMs": 200,
                    "transcript": "open report.pdf in Downloads",
                }
            ],
        }

    clip = canonical_clips()[0]
    stt = MuseFileTranscriber("test-key", transport=transport)
    result = stt.transcribe(clip.speech, SAMPLE_RATE_HZ)
    assert result.text == "open report.pdf in Downloads"
    assert result.model == MUSE_ASR_MODEL
    assert result.endpointed is True
    assert result.error == ""
    assert captured["url"] == "https://api.meta.ai/v1/asr/transcribe"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == "Bearer test-key"
    body = captured["body"]
    assert isinstance(body, bytes)
    assert b"muse-voice-transcribe-1.0" in body
    assert b"ENDPOINTING" in body
    assert b"English" in body
    assert b"WAV" in body
    assert b"report.pdf" in body
    assert MUSE_STT_ESTIMATE_MS == 800


def test_missing_key_never_builds_a_live_transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    called = False

    def transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        nonlocal called
        called = True
        return {"transcript": "should not run"}

    stt = transcriber_from_env(transport=transport)
    clip = canonical_clips()[1]
    result = stt.transcribe(clip.speech, SAMPLE_RATE_HZ)
    assert called is False
    assert result.model == "fixture"
    assert result.text == "read the invoice total"

    monkeypatch.setenv("MODEL_API_KEY", "live-key")
    live = transcriber_from_env(transport=transport)
    assert isinstance(live, MuseFileTranscriber)
    assert live.transcribe(clip.speech, SAMPLE_RATE_HZ).text == "should not run"
    assert called is True


def test_realtime_endpointing_uses_native_vad_events() -> None:
    session = MuseRealtimeSession("test-key", sample_rate=SAMPLE_RATE_HZ)
    handshake = session.handshake_payload()
    assert handshake["model"] == "muse-voice-transcribe-1.0"
    assert handshake["mode"] == "ENDPOINTING"
    assert handshake["audioEncoding"] == "PCM_16KHZ"
    assert handshake["authorization"]["accessToken"] == "Bearer test-key"
    assert handshake["languageBias"] == ["English"]
    assert session.websocket_url().startswith(MUSE_REALTIME_URL)

    events = (
        {"sessionId": "sess-1"},
        {"type": "speechStart", "turnId": 1, "audioProcessedMs": 40},
        {
            "type": "transcript",
            "transcript": "open report",
            "final": False,
            "audioProcessedMs": 120,
        },
        {"type": "speechEnd", "turnId": 1, "audioProcessedMs": 200},
        {
            "type": "speechComplete",
            "turnId": 1,
            "transcript": "open report.pdf in Downloads",
            "audioProcessedMs": 200,
        },
    )
    completed = []
    for event in events:
        completed.extend(session.feed_event(event))
    assert session.saw_speech_end is True
    assert [turn.text for turn in completed] == ["open report.pdf in Downloads"]
    assert completed[0].endpointed is True

    class FakeSocket:
        def __init__(self) -> None:
            self.sent: list[str | bytes] = []
            self._incoming = [
                '{"sessionId": "sess-1"}',
                '{"type": "speechStart", "turnId": 1, "audioProcessedMs": 40}',
                '{"type": "speechEnd", "turnId": 1, "audioProcessedMs": 80}',
                (
                    '{"type": "speechComplete", "turnId": 1, '
                    '"transcript": "attach the file", "audioProcessedMs": 80}'
                ),
            ]

        def send_text(self, data: str) -> None:
            self.sent.append(data)

        def send_bytes(self, data: bytes) -> None:
            self.sent.append(data)

        def recv(self) -> str | bytes | None:
            if self._incoming:
                return self._incoming.pop(0)
            return None

    socket = FakeSocket()
    turns = session.run(socket, [b"\x00\x01"])
    assert [turn.text for turn in turns] == ["attach the file"]
    assert any(isinstance(item, str) and "endStream" in item for item in socket.sent)
    assert socket.sent[0].startswith("{")
    assert b"muse-voice-transcribe-1.0" in socket.sent[0].encode()


def test_muse_transport_errors_become_an_empty_transcript() -> None:
    def transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        raise OSError("network down")

    result = MuseFileTranscriber("test-key", transport=transport).transcribe(
        b"\x00\x00",
        SAMPLE_RATE_HZ,
    )
    assert result.text == ""
    assert result.error == "network down"
    assert result.model == MUSE_ASR_MODEL
