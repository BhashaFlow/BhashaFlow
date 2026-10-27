"""Spoken demo loop: listen, ground, act, confirm, next."""

import pytest

from bhashaflow_audio.fixtures import CANONICAL_UTTERANCES
from bhashaflow_orchestrator.cli import main
from bhashaflow_orchestrator.demo import DemoLoop


def test_fixture_script_runs_by_voice_without_a_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_keyboard(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("keyboard")

    monkeypatch.setattr("builtins.input", refuse_keyboard)
    loop = DemoLoop.for_fixture()
    report = loop.run()
    assert report.ok is True
    assert report.woke is True
    assert report.stopped is True
    assert report.commands == list(CANONICAL_UTTERANCES)
    assert report.recoveries == 0
    assert report.confirmations[0] == "Listening"
    assert "Opening report.pdf" in report.confirmations
    assert "Reading the invoice" in report.confirmations
    assert "Focusing the recipient" in report.confirmations
    assert "Attaching the file" in report.confirmations
    assert report.confirmations[-1] == "Stopped"
    text = report.text()
    assert "phase=listen" in text
    assert "phase=ground" in text
    assert "phase=act" in text
    assert "phase=confirm" in text
    assert "phase=next" in text
    assert "phase=abort" in text
    assert "phase=done" in text
    assert "indicator=thinking" in text
    assert "indicator=acting" in text
    assert "indicator=confirming" in text
    assert "focus_stolen=false" in text
    assert 'target="report.pdf"' in text or "target=report.pdf" in text
    assert "app=Files" in text
    assert "app=Mail" in text
    engine = loop._actions
    assert "Files" in engine.opened
    assert "Mail" in engine.opened
    assert engine.typed == [("To", "demo@bhashaflow.test")]


def test_a_recoverable_click_is_retried_once() -> None:
    loop = DemoLoop.for_fixture(fail_once=frozenset({"click:report.pdf"}))
    report = loop.run()
    assert report.recoveries == 1
    assert report.ok is True
    assert "Trying that again" in report.confirmations
    assert report.failures == 0
    assert loop._actions.clicks[0] == "report.pdf"


def test_cli_prints_the_stage_log_and_recovers_once(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "phase=done" in output
    assert "ok=true" in output
    assert "steps=4" in output
    assert "recoveries=1" in output
    assert 'text="Trying that again"' in output
    assert "focus_stolen=false" in output


def test_no_recover_runs_the_clean_script(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-recover"]) == 0
    output = capsys.readouterr().out
    assert "recoveries=0" in output
    assert "ok=true" in output


def test_mic_without_a_key_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert main(["--mic"]) == 2
    assert "MODEL_API_KEY" in capsys.readouterr().err


def test_desktop_build_does_not_inject(monkeypatch: pytest.MonkeyPatch) -> None:
    from bhashaflow_action.desktop import DesktopActionEngine
    from bhashaflow_orchestrator.cli import build_demo

    monkeypatch.delenv("BHASHAFLOW_ACTIONS", raising=False)
    loop = build_demo(desktop=True)
    assert isinstance(loop._actions, DesktopActionEngine)


def test_muse_planner_flag_refuses_to_run_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert main(["--planner", "muse"]) == 2
    assert "MODEL_API_KEY" in capsys.readouterr().err
