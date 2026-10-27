from pathlib import Path

from bhashaflow_audio.budget import (
    BARGE_IN_BUDGET_MS,
    END_OF_UTTERANCE_MS,
    FIXTURE_STT_BUDGET_MS,
    MUSE_STT_ESTIMATE_MS,
    TTS_CONFIRM_BUDGET_MS,
    VAD_DECISION_BUDGET_MS,
)


def test_audio_doc_states_latency_muse_stt_and_the_tts_gap() -> None:
    root = Path(__file__).resolve().parents[3]
    doc = (root / "docs" / "audio-pipeline.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for text in (doc, readme):
        assert f"{VAD_DECISION_BUDGET_MS} ms" in text
        assert f"{END_OF_UTTERANCE_MS} ms" in text
        assert f"{FIXTURE_STT_BUDGET_MS} ms" in text
        assert f"{TTS_CONFIRM_BUDGET_MS} ms" in text
        assert f"{BARGE_IN_BUDGET_MS} ms" in text
    assert "muse-voice-transcribe-1.0" in doc
    assert "wss://api.meta.ai/v1/asr/realtime" in doc
    assert "https://api.meta.ai/v1/asr/transcribe" in doc
    assert "Muse has no TTS" in doc
    assert "non-Muse" in doc
    assert "barge-in" in doc
    assert "ambient" in doc
    assert str(MUSE_STT_ESTIMATE_MS) in doc
    assert "python -m bhashaflow_audio" in readme
    assert VAD_DECISION_BUDGET_MS == 30
    assert END_OF_UTTERANCE_MS == 400
    assert FIXTURE_STT_BUDGET_MS == 50
    assert TTS_CONFIRM_BUDGET_MS == 150
    assert BARGE_IN_BUDGET_MS == 100
