from pathlib import Path


def test_runbook_covers_permissions_env_warmup_abort_and_signoff() -> None:
    root = Path(__file__).resolve().parents[3]
    text = (root / "docs" / "demo-runbook.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "uv run bhashaflow-demo" in text
    assert "--no-recover" in text
    assert "recoveries=1" in text
    assert "Trying that again" in text
    assert "Accessibility" in text
    assert "Screen recording" in text
    assert "Microphone" in text
    assert "MODEL_API_KEY" in text
    assert "BHASHAFLOW_ACTIONS" in text
    assert "BHASHAFLOW_PLANNER" in text
    assert "muse-spark-1.3" in text
    assert "muse-wonder-1.0" in text
    assert "muse-voice-transcribe-1.0" in text
    assert "Muse has no TTS" in text
    assert "Warm-up" in text
    assert "stop" in text
    assert "Ctrl-C" in text
    assert "allowlist" in text.casefold() or "Files" in text
    for name in ("Lungile", "Alucard", "Satinder"):
        assert name in text
    assert "ML (Lungile)" in text
    assert "Audio (Alucard)" in text
    assert "Arch (Satinder)" in text
    assert "demo-runbook.md" in readme
