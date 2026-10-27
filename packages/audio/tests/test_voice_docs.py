from pathlib import Path


def test_voice_doc_describes_the_hands_off_control_plane() -> None:
    root = Path(__file__).resolve().parents[3]
    doc = (root / "docs" / "voice-control.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for text in (doc, readme):
        assert "listening" in text
        assert "thinking" in text
        assert "acting" in text
        assert "bhashaflow start" in text
    assert "stop" in doc
    assert "keyboard" in doc.casefold()
    assert "focus" in doc.casefold()
    assert "python -m bhashaflow_audio.control" in readme
