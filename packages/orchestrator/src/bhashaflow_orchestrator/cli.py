"""Single entrypoint for the spoken demo script.

``uv run bhashaflow-demo`` plays fixture audio through listen → ground → act
→ confirm, including one rehearsed click miss that recovers. It does not read
the keyboard. Muse runs only with ``--planner muse`` and an API key.
``--desktop`` selects live capture. OS input stays off unless
``BHASHAFLOW_ACTIONS=desktop`` as well, and the rehearsed miss is skipped.
"""

import argparse
import os
import sys

from bhashaflow_action import FixtureActionEngine
from bhashaflow_action.desktop import DesktopActionEngine
from bhashaflow_audio.muse import MuseFileTranscriber, muse_api_key
from bhashaflow_audio.pipeline import AudioPipeline
from bhashaflow_audio.sources import MicrophoneUnavailable, open_microphone
from bhashaflow_audio.stt import FixtureTranscriber, SpeechToText
from bhashaflow_audio.tts import StatusSynthesizer
from bhashaflow_orchestrator.demo import SCRIPT_SCENES, DemoLoop
from bhashaflow_orchestrator.loop import PlannerLoop
from bhashaflow_orchestrator.muse_planner import MuseSparkAttention
from bhashaflow_vision.capture import DesktopCapture
from bhashaflow_vision.grounding import AttentionModel, FixtureAttention
from bhashaflow_vision.session import VisionSession

# First click of report.pdf fails once so the loop can show a spoken retry.
REHEARSED_MISS = frozenset({"click:report.pdf"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bhashaflow-demo")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Single-user desktop agent. Requires a Muse key, a microphone, and OS permissions",
    )
    parser.add_argument(
        "--planner",
        choices=("fixture", "muse"),
        default=None,
        help="fixture (default, no network) or muse (muse-spark-1.3, needs a key)",
    )
    parser.add_argument(
        "--no-recover",
        action="store_true",
        help="Skip the rehearsed click miss and run the clean script",
    )
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Desktop capture. OS commands also need BHASHAFLOW_ACTIONS=desktop",
    )
    parser.add_argument(
        "--mic",
        action="store_true",
        help="Read the microphone. Needs a Model API key and OS microphone permission",
    )
    args = parser.parse_args(argv)
    if args.live:
        if args.planner == "fixture":
            print(
                "bhashaflow-demo --live does not use the fixture planner. "
                "Omit --planner, or pass --planner muse. "
                "The keyless rehearsal is: uv run bhashaflow-demo",
                file=sys.stderr,
            )
            return 2
        from bhashaflow_orchestrator.live import run_live

        return run_live()
    planner_mode = "fixture" if args.planner is None else args.planner
    if planner_mode == "muse" and not muse_api_key():
        print("muse planner needs MODEL_API_KEY or BHASHAFLOW_MUSE_API_KEY", file=sys.stderr)
        return 2
    if args.mic and not muse_api_key():
        print("live mic needs MODEL_API_KEY; rehearse with the fixture command", file=sys.stderr)
        return 2
    source = None
    if args.mic:
        try:
            source = open_microphone()
        except MicrophoneUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 2
    recover = not args.no_recover and not args.desktop
    stt = MuseFileTranscriber(muse_api_key()) if args.mic else None
    try:
        report = build_demo(
            planner_mode=planner_mode,
            recover=recover,
            desktop=args.desktop,
            stt=stt,
        ).run(source)
    except KeyboardInterrupt:
        print("phase=abort reason=keyboard")
        return 130
    print(report.text())
    return 0 if report.ok else 1


def build_demo(
    *,
    planner_mode: str = "fixture",
    recover: bool = True,
    desktop: bool = False,
    stt: SpeechToText | None = None,
) -> DemoLoop:
    """Wire one loop. ``recover`` arms the rehearsed miss on the fixture engine."""
    voice = StatusSynthesizer()
    planner = _planner(planner_mode, desktop=desktop)
    transcriber = FixtureTranscriber() if stt is None else stt
    if desktop:
        actions: FixtureActionEngine | DesktopActionEngine = DesktopActionEngine(_desktop_runner())
        scenes: tuple[str, ...] = ()
    else:
        fail_once = REHEARSED_MISS if recover else frozenset()
        actions = FixtureActionEngine(fail_once=fail_once)
        scenes = SCRIPT_SCENES
    pipeline = AudioPipeline(transcriber, voice)
    return DemoLoop(planner, actions, pipeline, voice, scenes=scenes)


def _planner(planner_mode: str, *, desktop: bool) -> PlannerLoop:
    model: AttentionModel
    if planner_mode == "muse":
        model = MuseSparkAttention(muse_api_key())
    else:
        model = FixtureAttention()
    if desktop:
        return PlannerLoop(VisionSession(DesktopCapture(), model))
    return PlannerLoop(VisionSession.for_demo_script(model=model))


def _desktop_runner():
    if os.environ.get("BHASHAFLOW_ACTIONS", "").strip().casefold() == "desktop":
        from bhashaflow_action.desktop import _subprocess_runner

        return _subprocess_runner
    return _refuse_runner


def _refuse_runner(argv: list[str]) -> int:
    """``--desktop`` without the actions env var logs the command and does not run it."""
    print("refusing OS input; set BHASHAFLOW_ACTIONS=desktop to allow it", file=sys.stderr)
    print("argv=" + " ".join(argv), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
