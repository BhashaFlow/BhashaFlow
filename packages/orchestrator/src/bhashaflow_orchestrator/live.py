"""Single-user desktop agent.

``bhashaflow`` and ``bhashaflow-demo --live`` listen on the microphone, transcribe
with Muse, ground with muse-spark-1.3, and click or type on the allowlist.
They exit 2 when the key or an OS helper is missing. They do not switch to the
fixture catalog, the fixture planner, or the in-memory action engine.

``bhashaflow --fixture`` is the explicit rehearsal and matches ``bhashaflow-demo``.
"""

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bhashaflow_action import desktop as desktop_actions
from bhashaflow_action.desktop import DesktopActionEngine, action_runtime_status
from bhashaflow_audio.muse import MUSE_ASR_MODEL, MuseFileTranscriber, MuseRealtimeSession
from bhashaflow_audio.pipeline import AudioPipeline
from bhashaflow_audio.realtime import (
    RealtimeUnavailable,
    RealtimeUtterancePipeline,
    connect_muse_realtime,
)
from bhashaflow_audio.sources import MicrophoneUnavailable, microphone_status, open_microphone
from bhashaflow_audio.tts import synthesizer_from_env
from bhashaflow_orchestrator.config import AgentConfig, ConfigError, load_env_file, parse_config
from bhashaflow_orchestrator.demo import DemoLoop
from bhashaflow_orchestrator.log import StageLog, json_stderr_sink
from bhashaflow_orchestrator.loop import PlannerLoop
from bhashaflow_orchestrator.muse_planner import SPARK_MODEL, LiveSparkGrounder, MuseSparkAttention
from bhashaflow_vision.capture import DesktopCapture, desktop_capture_status
from bhashaflow_vision.sam import SamRegion
from bhashaflow_vision.session import VisionSession

Probe = Callable[[], tuple[bool, str]]
Connect = Callable[[], object]


class LiveStartupError(RuntimeError):
    """The live path refused to start. The message is safe to print."""


@dataclass(frozen=True)
class LiveProbes:
    """OS checks. Tests replace these so CI never opens a device."""

    microphone: Probe
    capture: Probe
    actions: Probe


@dataclass(frozen=True)
class SttChoice:
    """Which Muse transcription transport the session will use."""

    transport: str
    reason: str
    model: str = MUSE_ASR_MODEL
    socket: object | None = None
    session: MuseRealtimeSession | None = None


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="bhashaflow")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Explicit keyless rehearsal. This is the only fixture path on this command",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional KEY=value file. Exported variables win. Defaults to .env",
    )
    args = parser.parse_args(argv)
    if args.fixture:
        from bhashaflow_orchestrator.cli import main as demo_main

        return demo_main([])
    return run_live(env_file=args.env_file)


def run_live(
    *,
    env_file: str | None = None,
    probes: LiveProbes | None = None,
    connect_realtime: Connect | None = None,
) -> int:
    """Validate, then run one live session. Missing requirements exit 2."""
    if env_file is not None:
        path = Path(env_file)
    else:
        path = Path(os.environ.get("BHASHAFLOW_ENV_FILE", ".env"))
    load_env_file(path)
    try:
        config = parse_config(os.environ, mode="live")
    except ConfigError as exc:
        print(f"config: {exc}", file=sys.stderr)
        return 2
    active = probes or LiveProbes(
        microphone=microphone_status,
        capture=_capture_probe,
        actions=action_runtime_status,
    )
    problems = live_blockers(config, active)
    if problems:
        print("bhashaflow live mode cannot start.", file=sys.stderr)
        for item in problems:
            print(f"- {item}", file=sys.stderr)
        print(
            "Live mode does not fall back to the fixture rehearsal. "
            "Run uv run bhashaflow-demo for the keyless script, "
            "or uv run bhashaflow --fixture.",
            file=sys.stderr,
        )
        return 2
    connect = connect_realtime or (lambda: _connect(config.api_key, config.muse_timeout_s))
    try:
        choice = choose_stt(config, connect)
    except LiveStartupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        source = open_microphone()
    except MicrophoneUnavailable as exc:
        print(str(exc), file=sys.stderr)
        print("Live mode does not fall back to fixture audio.", file=sys.stderr)
        return 2
    loop = build_live_demo(config, choice)
    loop.log.event(
        phase="startup",
        mode="live",
        stt=choice.model,
        stt_transport=choice.transport,
        stt_reason=choice.reason,
        planner=SPARK_MODEL,
        actions="desktop",
        tts=config.tts_backend,
        api_key="set",
        sam=config.sam,
    )
    try:
        try:
            report = loop.run(source)
        except KeyboardInterrupt:
            print("phase=abort reason=keyboard")
            return 130
    finally:
        close = getattr(loop._pipeline, "close", None)
        if close is not None:
            close()
    print(report.text())
    return 0 if report.ok else 1


def live_blockers(config: AgentConfig, probes: LiveProbes) -> list[str]:
    """Every reason the live path should stop, including OS probes."""
    problems: list[str] = []
    if not config.api_key:
        problems.append(
            "Set MODEL_API_KEY, BHASHAFLOW_MUSE_API_KEY, or BHASHAFLOW_STT_API_KEY. "
            "Live mode does not fall back to fixture transcripts."
        )
    if config.actions != "desktop":
        problems.append(
            "BHASHAFLOW_ACTIONS is not desktop. Live mode does not pretend to click. "
            "Unset it or set BHASHAFLOW_ACTIONS=desktop."
        )
    if config.capture != "desktop":
        problems.append(
            "BHASHAFLOW_CAPTURE is not desktop. Live mode does not ground fixture scenes. "
            "Unset it or set BHASHAFLOW_CAPTURE=desktop."
        )
    if config.planner != "muse":
        problems.append(
            "BHASHAFLOW_PLANNER is not muse. Live grounding is muse-spark-1.3 only. "
            "Unset it or set BHASHAFLOW_PLANNER=muse."
        )
    if config.stt == "fixture":
        problems.append(
            "BHASHAFLOW_STT=fixture is the keyless catalog. "
            "Use auto, file, or realtime. Live mode will not use fixture transcripts."
        )
    if config.tts_backend == "command" and not config.tts_command:
        problems.append(
            "BHASHAFLOW_TTS_BACKEND=command needs BHASHAFLOW_TTS_COMMAND. "
            "That program is optional non-Muse speech. Muse has no TTS model. "
            "Or set BHASHAFLOW_TTS_BACKEND=status."
        )
    for probe in (probes.microphone, probes.capture, probes.actions):
        ok, detail = probe()
        if not ok:
            problems.append(detail)
    return problems


def choose_stt(config: AgentConfig, connect: Connect) -> SttChoice:
    """Pick Muse file or Muse realtime. Fixture transcripts are refused."""
    if config.stt == "fixture":
        raise LiveStartupError(
            "BHASHAFLOW_STT=fixture is the keyless catalog. "
            "Live mode will not use fixture transcripts. Set auto, file, or realtime."
        )
    if config.stt == "file":
        return SttChoice("file", "BHASHAFLOW_STT=file")
    try:
        opened = connect()
    except RealtimeUnavailable as exc:
        if config.stt == "realtime":
            raise LiveStartupError(
                "Muse realtime STT failed: "
                + str(exc)
                + ". Live mode will not use fixture transcripts. "
                "Set BHASHAFLOW_STT=file to use muse-voice-transcribe-1.0 file transcription."
            ) from exc
        return SttChoice("file", str(exc))
    session = opened if isinstance(opened, MuseRealtimeSession) else None
    socket = opened if session is None else None
    if isinstance(opened, tuple) and len(opened) == 2:
        socket, session = opened
    return SttChoice("realtime", "connected", socket=socket, session=session)


def build_live_demo(config: AgentConfig, choice: SttChoice) -> DemoLoop:
    """Wire mic transcription, Spark, and the desktop action engine."""
    log = StageLog(sink=json_stderr_sink(config.log_level), secrets=(config.api_key,))
    tts = synthesizer_from_env()
    if choice.transport == "realtime" and choice.socket is not None:
        session = choice.session or MuseRealtimeSession(config.api_key)
        pipeline: AudioPipeline | RealtimeUtterancePipeline = RealtimeUtterancePipeline(
            choice.socket,  # type: ignore[arg-type]
            session,
            tts,
        )
    else:
        pipeline = AudioPipeline(
            MuseFileTranscriber(
                config.api_key,
                retries=config.muse_retries,
                timeout_s=config.muse_timeout_s,
            ),
            tts,
        )
    spark = MuseSparkAttention(
        config.api_key,
        timeout_s=config.muse_timeout_s,
        retries=config.muse_retries,
        strict=True,
    )
    sam = None
    if config.sam:
        sam = SamRegion(
            config.api_key,
            transport=_sam_transport,
            retries=config.muse_retries,
            timeout_s=config.muse_timeout_s,
        )
    model = LiveSparkGrounder(spark, sam)
    planner = PlannerLoop(VisionSession(DesktopCapture(), model))
    actions = DesktopActionEngine(desktop_actions._subprocess_runner)
    return DemoLoop(
        planner,
        actions,
        pipeline,  # type: ignore[arg-type]
        tts,
        scenes=(),
        log=log,
        require_script=False,
    )


def _connect(api_key: str, timeout_s: float) -> tuple[object, MuseRealtimeSession]:
    session = MuseRealtimeSession(api_key)
    socket = connect_muse_realtime(session.websocket_url(), timeout_s=min(5.0, timeout_s))
    return socket, session


def _capture_probe() -> tuple[bool, str]:
    status = desktop_capture_status()
    if status.available:
        return True, status.detail
    return False, (
        "Screen capture is unavailable ("
        + status.detail
        + "). Grant screen recording to this process (macOS Screen Recording, "
        "Windows graphics capture, or a Linux portal or X11). "
        "Live mode does not ground fixture scenes."
    )


def _sam_transport(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, object]:
    from bhashaflow_orchestrator.muse_planner import _urllib_transport

    return _urllib_transport(url, body, headers, timeout)
