"""Voice-first control plane. No keyboard, no focus-stealing window."""

import pytest

from bhashaflow_audio.control import VoiceControl, run_spoken_demo
from bhashaflow_audio.fixtures import (
    CANONICAL_UTTERANCES,
    WAKE_UTTERANCE,
    canonical_clips,
    make_clip,
)
from bhashaflow_audio.sources import FixtureSource
from bhashaflow_audio.tts import StatusSynthesizer


def test_commands_wait_for_a_spoken_wake() -> None:
    control = VoiceControl(StatusSynthesizer())
    result = control.run(FixtureSource(canonical_clips()))
    assert result.commands == []
    assert result.woke is False
    assert result.indicator == "idle"


def test_spoken_demo_finishes_hands_off_the_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_keyboard(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("keyboard")

    monkeypatch.setattr("builtins.input", refuse_keyboard)
    result = run_spoken_demo()
    assert result.woke is True
    assert result.stopped is True
    assert result.commands == list(CANONICAL_UTTERANCES)
    assert result.confirmations[0] == "Listening"
    assert "Opening report.pdf" in result.confirmations
    assert "Reading the invoice" in result.confirmations
    assert "Focusing the recipient" in result.confirmations
    assert "Attaching the file" in result.confirmations
    assert result.confirmations[-1] == "Stopped"
    names = {event.indicator for event in result.events}
    assert {"listening", "thinking", "acting", "confirming", "idle"} <= names
    assert all(event.focus_stolen is False for event in result.events)
    assert all(len(line) <= 40 for line in result.confirmations)


def test_stop_ends_the_session_before_later_commands() -> None:
    clips = (
        make_clip(WAKE_UTTERANCE),
        canonical_clips()[0],
        make_clip("stop"),
        canonical_clips()[1],
    )
    result = VoiceControl(StatusSynthesizer()).run(FixtureSource(clips))
    assert result.commands == ["open report.pdf in Downloads"]
    assert result.stopped is True
    assert result.indicator == "idle"


def test_indicator_file_tracks_the_phase(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "status.txt"
    result = VoiceControl(StatusSynthesizer(), status_path=path).run(
        FixtureSource((make_clip(WAKE_UTTERANCE), make_clip("abort")))
    )
    assert result.stopped is True
    assert path.read_text(encoding="utf-8").strip() == "idle"
