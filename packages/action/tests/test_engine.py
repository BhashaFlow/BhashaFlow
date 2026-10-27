"""Allowlisted click, type, focus, and open-app primitives."""

import platform

import pytest

from bhashaflow_action import DEMO_ALLOWLIST, FixtureActionEngine, perform
from bhashaflow_action.desktop import DesktopActionEngine, actions_from_env
from bhashaflow_action.engine import DEMO_RECIPIENT
from bhashaflow_vision.pointer import FocusSession
from bhashaflow_vision.session import VisionSession

PDF_PATH = (
    ("downloads", "open report.pdf in Downloads", "report.pdf", "click", ""),
    ("pdf", "read the invoice total", "Invoice total", "click", ""),
    ("mail", "focus the recipient", "To", "type", DEMO_RECIPIENT),
    ("mail", "attach the file", "Attach", "click", ""),
)


def _drive(engine: FixtureActionEngine) -> list[object]:
    session = VisionSession.for_demo_script()
    focus = FocusSession()
    outcomes = []
    for scene, utterance, _name, _kind, typed in PDF_PATH:
        session.show(scene)
        session.tick()
        handoff = focus.consume(session.ground(utterance))
        results = perform(engine, handoff, type_text=typed)
        assert results[-1].ok is True
        outcomes.append(results[-1])
    return outcomes


def test_fixture_script_drives_at_least_two_allowlisted_apps() -> None:
    engine = FixtureActionEngine()
    _drive(engine)
    assert engine.opened[0] == "Files"
    assert "Preview" in engine.opened
    assert "Mail" in engine.opened
    assert len({*engine.opened} & set(DEMO_ALLOWLIST)) >= 2
    assert engine.clicks == ["report.pdf", "Invoice total", "Attach"]
    assert engine.typed == [("To", DEMO_RECIPIENT)]
    assert engine.front_app == "Mail"
    assert "Terminal" not in DEMO_ALLOWLIST
    assert "Files" in DEMO_ALLOWLIST


def test_click_miss_is_recoverable_once() -> None:
    engine = FixtureActionEngine(fail_once=frozenset({"click:report.pdf"}))
    session = VisionSession.for_demo_script()
    session.show("downloads")
    session.tick()
    handoff = FocusSession().consume(session.ground("open report.pdf in Downloads"))
    first = perform(engine, handoff, type_text="")
    assert first[-1].ok is False
    assert first[-1].recoverable is True
    assert first[-1].reason == "click missed"
    second = perform(engine, handoff, type_text="")
    assert second[-1].ok is True
    assert engine.clicks == ["report.pdf"]


def test_low_confidence_handoff_stays_recoverable() -> None:
    session = VisionSession.for_demo_script()
    session.show("downloads")
    session.tick()
    handoff = FocusSession().consume(session.ground("delete the system partition"))
    results = perform(FixtureActionEngine(), handoff, type_text="")
    assert results[0].ok is False
    assert results[0].recoverable is True
    assert results[0].target_name == ""


def test_apps_outside_the_allowlist_are_refused() -> None:
    engine = FixtureActionEngine()
    for app in ("Terminal", "Safari", ""):
        opened = engine.open_app(app)
        assert opened.ok is False
        assert opened.recoverable is False
        assert opened.reason == "app not on demo allowlist"
    assert engine.opened == []
    typed = engine.type_text_raw("Mail", "To", "line\nwith control")
    assert typed.ok is False
    assert typed.recoverable is False
    assert typed.reason == "text rejected"


def test_desktop_runner_is_allowlisted_and_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BHASHAFLOW_ACTIONS", raising=False)
    assert isinstance(actions_from_env(), FixtureActionEngine)

    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    desktop = DesktopActionEngine(runner)
    refused = desktop.open_app("Terminal")
    assert refused.ok is False
    assert calls == []

    session = VisionSession.for_demo_script()
    session.show("mail")
    session.tick()
    handoff = FocusSession().consume(session.ground("attach the file"))
    assert handoff.target is not None
    clicked = desktop.click(handoff.target)
    assert clicked.ok is True
    assert calls[0][0] == "xdotool"
    assert str(handoff.target.x) in calls[0]
    assert str(handoff.target.y) in calls[0]

    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    opened = desktop.open_app("Mail")
    assert opened.ok is True
    assert calls[-1] == ["open", "-a", "Mail"]

    monkeypatch.setenv("BHASHAFLOW_ACTIONS", "desktop")
    selected = actions_from_env(runner)
    assert isinstance(selected, DesktopActionEngine)
    monkeypatch.setenv("BHASHAFLOW_ACTIONS", "yolo")
    assert isinstance(actions_from_env(runner), FixtureActionEngine)


def test_windows_click_and_type_inject_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    desktop = DesktopActionEngine(runner)
    session = VisionSession.for_demo_script()
    session.show("mail")
    session.tick()
    handoff = FocusSession().consume(session.ground("attach the file"))
    assert handoff.target is not None
    clicked = desktop.click(handoff.target)
    assert clicked.ok is True
    command = " ".join(calls[-1])
    assert "SetCursorPos" in command
    assert "mouse_event" in command
    assert str(handoff.target.x) in command
    assert str(handoff.target.y) in command
    assert "skipped" not in command.casefold()
    typed = desktop.type_text(handoff.target, "a+b")
    assert typed.ok is True
    typed_command = " ".join(calls[-1])
    assert "SendWait" in typed_command
    assert "{+}" in typed_command
    assert "skipped" not in typed_command.casefold()
