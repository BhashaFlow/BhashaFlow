"""Production entrypoint: fail loud, never silently rehearse."""

import json
import platform
from pathlib import Path

import pytest

from bhashaflow_audio.fixtures import make_clip
from bhashaflow_audio.sources import MicrophoneSource
from bhashaflow_orchestrator.cli import main
from bhashaflow_orchestrator.config import ConfigError, parse_config
from bhashaflow_orchestrator.live import LiveProbes, LiveStartupError, choose_stt, run_live
from bhashaflow_orchestrator.textutil import typed_text_from_utterance
from bhashaflow_vision.types import ScreenFrame

SECRET = "super-secret-key"


def _clear_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "MODEL_API_KEY",
        "BHASHAFLOW_MUSE_API_KEY",
        "BHASHAFLOW_STT_API_KEY",
        "BHASHAFLOW_ACTIONS",
        "BHASHAFLOW_CAPTURE",
        "BHASHAFLOW_PLANNER",
        "BHASHAFLOW_STT",
        "BHASHAFLOW_SAM",
        "BHASHAFLOW_TTS_BACKEND",
        "BHASHAFLOW_TTS_COMMAND",
        "BHASHAFLOW_MUSE_RETRIES",
        "BHASHAFLOW_MUSE_TIMEOUT_S",
        "BHASHAFLOW_LOG_LEVEL",
        "BHASHAFLOW_LOG_FORMAT",
    ):
        monkeypatch.delenv(name, raising=False)


def _ready_probes() -> LiveProbes:
    return LiveProbes(
        microphone=lambda: (True, "microphone ok"),
        capture=lambda: (True, "screen ok"),
        actions=lambda: (True, "input helper ok"),
    )


def test_parse_config_rejects_malformed_values() -> None:
    with pytest.raises(ConfigError, match="BHASHAFLOW_MUSE_RETRIES"):
        parse_config({"BHASHAFLOW_MUSE_RETRIES": "lots"}, mode="live")
    with pytest.raises(ConfigError, match="BHASHAFLOW_MUSE_TIMEOUT_S"):
        parse_config({"BHASHAFLOW_MUSE_TIMEOUT_S": "0"}, mode="live")
    with pytest.raises(ConfigError, match="BHASHAFLOW_LOG_LEVEL"):
        parse_config({"BHASHAFLOW_LOG_LEVEL": "verbose"}, mode="live")
    with pytest.raises(ConfigError, match="BHASHAFLOW_ACTIONS"):
        parse_config({"BHASHAFLOW_ACTIONS": "yolo"}, mode="live")
    with pytest.raises(ConfigError, match="BHASHAFLOW_TTS_BACKEND"):
        parse_config({"BHASHAFLOW_TTS_BACKEND": "cloud"}, mode="live")
    with pytest.raises(ConfigError, match="BHASHAFLOW_SAM"):
        parse_config({"BHASHAFLOW_SAM": "yes"}, mode="live")


def test_live_defaults_turn_on_the_desktop_stack() -> None:
    config = parse_config({"MODEL_API_KEY": SECRET}, mode="live")
    assert config.actions == "desktop"
    assert config.capture == "desktop"
    assert config.planner == "muse"
    assert config.stt == "auto"
    assert config.api_key == SECRET
    assert "super-secret-key" not in repr(config)
    fixture = parse_config({}, mode="fixture")
    assert fixture.actions == "fixture"
    assert fixture.planner == "fixture"
    assert fixture.api_key == ""


def test_missing_key_exits_nonzero_and_does_not_open_a_mic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    opened = {"mic": False}

    def explode() -> None:
        opened["mic"] = True
        raise AssertionError("microphone")

    monkeypatch.setattr("bhashaflow_orchestrator.live.open_microphone", explode)
    code = run_live(probes=_ready_probes(), env_file=str(Path("/tmp/bhashaflow-missing.env")))
    assert code == 2
    assert opened["mic"] is False
    error = capsys.readouterr().err
    assert "MODEL_API_KEY" in error
    assert "fixture" in error.casefold()


def test_explicit_fixture_env_is_not_a_silent_fallback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    monkeypatch.setenv("BHASHAFLOW_ACTIONS", "fixture")
    monkeypatch.setenv("BHASHAFLOW_PLANNER", "fixture")
    code = run_live(probes=_ready_probes(), env_file=str(Path("/tmp/bhashaflow-missing.env")))
    assert code == 2
    error = capsys.readouterr().err
    assert "BHASHAFLOW_ACTIONS" in error
    assert "muse-spark-1.3" in error
    assert SECRET not in error


def test_env_file_loads_the_key_without_printing_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    secret = "from-dotenv-secret-value"
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"export MODEL_API_KEY={secret}\nBHASHAFLOW_LOG_LEVEL=info\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BHASHAFLOW_STT", "file")
    code = run_live(
        env_file=str(env_file),
        probes=LiveProbes(
            microphone=lambda: (False, "mic blocked for test"),
            capture=lambda: (True, "screen ok"),
            actions=lambda: (True, "input helper ok"),
        ),
    )
    assert code == 2
    error = capsys.readouterr().err
    assert "mic blocked for test" in error
    assert "MODEL_API_KEY" not in error
    assert secret not in error


def test_env_file_does_not_override_exported_variables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from bhashaflow_orchestrator.config import load_env_file

    monkeypatch.setenv("MODEL_API_KEY", "already-exported-secret")
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_API_KEY=other-secret\n", encoding="utf-8")
    loaded = load_env_file(env_file)
    assert loaded == []
    assert __import__("os").environ["MODEL_API_KEY"] == "already-exported-secret"


def test_fixture_command_does_not_load_dotenv_or_call_muse(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    secret = "dotenv-should-stay-unread"
    env_file = tmp_path / ".env"
    env_file.write_text(f"MODEL_API_KEY={secret}\nBHASHAFLOW_PLANNER=muse\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "recoveries=1" in captured.out
    assert secret not in captured.out
    assert secret not in captured.err
    assert __import__("os").environ.get("MODEL_API_KEY", "") == ""


def test_live_flag_refuses_an_explicit_fixture_planner(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called = {"live": False}

    def mark(**_kwargs: object) -> int:
        called["live"] = True
        return 0

    monkeypatch.setattr("bhashaflow_orchestrator.live.run_live", mark)
    assert main(["--live", "--planner", "fixture"]) == 2
    assert called["live"] is False
    assert "fixture" in capsys.readouterr().err.casefold()


def test_demo_live_flag_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bhashaflow_orchestrator.live.run_live", lambda **_kwargs: 7)
    assert main(["--live"]) == 7


def test_choose_stt_file_is_muse_and_realtime_failure_is_explicit() -> None:
    config = parse_config({"MODEL_API_KEY": SECRET, "BHASHAFLOW_STT": "file"}, mode="live")

    def explode() -> object:
        raise AssertionError("connect")

    choice = choose_stt(config, explode)
    assert choice.transport == "file"
    assert choice.model == "muse-voice-transcribe-1.0"

    auto = parse_config({"MODEL_API_KEY": SECRET, "BHASHAFLOW_STT": "auto"}, mode="live")

    def refuse() -> object:
        from bhashaflow_audio.realtime import RealtimeUnavailable

        raise RealtimeUnavailable("socket refused")

    fallen = choose_stt(auto, refuse)
    assert fallen.transport == "file"
    assert fallen.model == "muse-voice-transcribe-1.0"
    assert "socket refused" in fallen.reason
    forced = parse_config({"MODEL_API_KEY": SECRET, "BHASHAFLOW_STT": "realtime"}, mode="live")
    with pytest.raises(LiveStartupError, match="fixture"):
        choose_stt(forced, refuse)


def test_typed_text_comes_from_the_utterance() -> None:
    assert typed_text_from_utterance("focus the recipient") == "demo@bhashaflow.test"
    assert typed_text_from_utterance('type "quarterly total"') == "quarterly total"
    assert typed_text_from_utterance("mail ada@example.com") == "ada@example.com"
    assert typed_text_from_utterance("type hello") == "hello"
    assert typed_text_from_utterance("open report.pdf") == ""


def _scripted_mic() -> MicrophoneSource:
    clips = (
        make_clip("bhashaflow start"),
        make_clip("open report.pdf in Downloads"),
        make_clip("stop"),
    )
    frames: list[bytes] = []
    for clip in clips:
        frames.append(clip.speech)
        frames.append(clip.silence)
    frames.append(b"")
    index = {"n": 0}

    def reader() -> bytes:
        frame = frames[index["n"]]
        index["n"] += 1
        return frame

    return MicrophoneSource(reader, sample_rate=clips[0].sample_rate)


def _frame() -> ScreenFrame:
    return ScreenFrame(
        frame_id=1,
        width=2,
        height=2,
        monotonic_ns=1,
        scene_id="desktop",
        app="",
        elements=(),
        pixels=b"\x00" * 12,
        encoding="rgb",
    )


def _install_live_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    spark_body: dict[str, object],
    runner_codes: dict[str, list[int]] | None = None,
) -> dict[str, object]:
    captured: dict[str, object] = {"stt": 0, "spark": 0, "argv": [], "spark_payloads": []}
    lines = ["bhashaflow start", "open report.pdf in Downloads", "stop"]

    def stt_transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["stt"] = int(captured["stt"]) + 1
        captured["stt_url"] = url
        text = lines[int(captured["stt"]) - 1]
        return {"transcript": text, "turns": [{"transcript": text}]}

    def spark_transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["spark"] = int(captured["spark"]) + 1
        captured["spark_payloads"].append(json.loads(body))  # type: ignore[union-attr]
        captured["timeout"] = timeout
        assert headers["authorization"] == f"Bearer {SECRET}"
        return {"choices": [{"message": {"content": json.dumps(spark_body)}}]}

    def runner(argv: list[str]) -> int:
        captured["argv"].append(argv)  # type: ignore[union-attr]
        if runner_codes is None:
            return 0
        queue = runner_codes.get(argv[0])
        if not queue:
            return 0
        return queue.pop(0)

    monkeypatch.setattr("bhashaflow_audio.muse._urllib_transport", stt_transport)
    monkeypatch.setattr("bhashaflow_orchestrator.muse_planner._urllib_transport", spark_transport)
    monkeypatch.setattr("bhashaflow_action.desktop._subprocess_runner", runner)
    monkeypatch.setattr("bhashaflow_orchestrator.live.open_microphone", _scripted_mic)
    monkeypatch.setattr(
        "bhashaflow_vision.capture.DesktopCapture.grab",
        lambda _self: _frame(),
    )

    def refuse_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("urllib")

    monkeypatch.setattr("urllib.request.urlopen", refuse_network)
    return captured


def test_live_path_uses_muse_spark_and_desktop_actions(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    monkeypatch.setenv("BHASHAFLOW_STT", "file")
    monkeypatch.setenv("BHASHAFLOW_MUSE_TIMEOUT_S", "6")
    captured = _install_live_fakes(
        monkeypatch,
        spark_body={
            "app": "Files",
            "action": "click",
            "name": "report.pdf",
            "x": 0,
            "y": 0,
            "width": 2,
            "height": 2,
            "confidence": 0.91,
        },
    )
    code = run_live(probes=_ready_probes(), env_file=str(Path("/tmp/bhashaflow-missing.env")))
    output = capsys.readouterr()
    assert code == 0, output.err + output.out
    assert "ok=true" in output.out
    assert "steps=1" in output.out
    assert captured["stt"] == 3
    assert captured["spark"] == 1
    payload = captured["spark_payloads"][0]
    assert isinstance(payload, dict)
    assert payload["model"] == "muse-spark-1.3"
    assert payload["reasoning_effort"] == "low"
    encoded = json.dumps(payload)
    assert "iVBORw0KGgo" in encoded
    assert "Files" in encoded
    argv = captured["argv"]
    assert isinstance(argv, list)
    joined = " ".join(" ".join(item) for item in argv)
    assert "Files" in joined
    assert "Terminal" not in joined
    system = platform.system()
    if system == "Linux":
        assert "xdg-open" in joined
        assert "xdotool" in joined
    elif system == "Darwin":
        assert "osascript" in joined
    elif system == "Windows":
        assert "powershell" in joined
    assert SECRET not in output.out
    assert SECRET not in output.err
    start = json.loads(output.err.strip().splitlines()[0])
    assert start["phase"] == "startup"
    assert start["stt"] == "muse-voice-transcribe-1.0"
    assert start["stt_transport"] == "file"
    assert start["planner"] == "muse-spark-1.3"
    assert start["api_key"] == "set"


def test_live_click_retries_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    monkeypatch.setenv("BHASHAFLOW_STT", "file")
    click = {"Linux": "xdotool", "Darwin": "osascript", "Windows": "powershell"}.get(
        platform.system(),
        "xdotool",
    )
    _install_live_fakes(
        monkeypatch,
        spark_body={
            "app": "Finder",
            "action": "click",
            "name": "report.pdf",
            "x": 0,
            "y": 0,
            "width": 2,
            "height": 2,
            "confidence": 0.9,
        },
        runner_codes={click: [1, 0]},
    )
    assert run_live(probes=_ready_probes(), env_file=str(Path("/tmp/bhashaflow-missing.env"))) == 0
    output = capsys.readouterr().out
    assert "recoveries=1" in output
    assert "Trying that again" in output
    assert "ok=true" in output


def test_live_refuses_apps_outside_the_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    monkeypatch.setenv("BHASHAFLOW_STT", "file")
    captured = _install_live_fakes(
        monkeypatch,
        spark_body={
            "app": "Terminal",
            "action": "click",
            "name": "shell",
            "x": 0,
            "y": 0,
            "width": 2,
            "height": 2,
            "confidence": 0.95,
        },
    )
    assert run_live(probes=_ready_probes(), env_file=str(Path("/tmp/bhashaflow-missing.env"))) == 1
    output = capsys.readouterr().out
    assert "app not on demo allowlist" in output
    assert captured["argv"] == []


def test_spark_transport_failure_does_not_fall_back_to_the_fixture(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    monkeypatch.setenv("BHASHAFLOW_STT", "file")
    monkeypatch.setenv("BHASHAFLOW_MUSE_RETRIES", "1")
    calls = {"spark": 0}

    lines = ["bhashaflow start", "open report.pdf in Downloads", "stop"]
    spoken = {"n": 0}

    def stt_transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        text = lines[spoken["n"]]
        spoken["n"] += 1
        return {"transcript": text, "turns": [{"transcript": text}]}

    def spark_transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        calls["spark"] += 1
        raise OSError(f"down {SECRET}")

    def refuse_fixture(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("fixture attention")

    monkeypatch.setattr("bhashaflow_audio.muse._urllib_transport", stt_transport)
    monkeypatch.setattr("bhashaflow_orchestrator.muse_planner._urllib_transport", spark_transport)
    monkeypatch.setattr("bhashaflow_vision.grounding.FixtureAttention", refuse_fixture)
    monkeypatch.setattr("bhashaflow_orchestrator.live.open_microphone", _scripted_mic)
    monkeypatch.setattr("bhashaflow_vision.capture.DesktopCapture.grab", lambda _self: _frame())
    monkeypatch.setattr("bhashaflow_action.desktop._subprocess_runner", lambda _argv: 0)
    code = run_live(probes=_ready_probes(), env_file=str(Path("/tmp/bhashaflow-missing.env")))
    captured = capsys.readouterr()
    assert code == 1
    assert calls["spark"] == 2
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert "[redacted]" in captured.out or "[redacted]" in captured.err
    assert "muse-spark-1.3" in captured.out


def test_bhashaflow_fixture_switch_is_the_rehearsal(capsys: pytest.CaptureFixture[str]) -> None:
    from bhashaflow_orchestrator.live import main as live_main

    assert live_main(["--fixture"]) == 0
    assert "recoveries=1" in capsys.readouterr().out


def test_production_doc_states_the_live_path_and_the_gaps() -> None:
    root = Path(__file__).resolve().parents[3]
    text = (root / "docs" / "production.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "uv run bhashaflow",
        "bhashaflow-demo --live",
        "MODEL_API_KEY",
        "muse-voice-transcribe-1.0",
        "muse-spark-1.3",
        "muse-wonder-1.0",
        "sam-3.1",
        "Muse has no TTS",
        "multi-tenant",
        "billing",
        "Windows",
        "macOS",
        "Linux",
        "allowlist",
        "xdotool",
        "Accessibility",
        "Ctrl-C",
        "BHASHAFLOW_ACTIONS",
    ):
        assert phrase in text
    assert "uv run bhashaflow" in readme
    assert "docs/production.md" in readme
