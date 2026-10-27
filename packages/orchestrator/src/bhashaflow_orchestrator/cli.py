"""Single entrypoint for the spoken demo script.

``uv run bhashaflow-demo`` plays fixture audio through listen → ground → act
→ confirm. It does not read the keyboard and does not call Muse unless
``--planner muse`` is set and a Model API key is present.
"""

import argparse
import sys

from bhashaflow_action import FixtureActionEngine
from bhashaflow_audio.muse import muse_api_key
from bhashaflow_audio.pipeline import AudioPipeline
from bhashaflow_audio.stt import FixtureTranscriber
from bhashaflow_audio.tts import StatusSynthesizer
from bhashaflow_orchestrator.demo import DemoLoop
from bhashaflow_orchestrator.loop import PlannerLoop
from bhashaflow_orchestrator.muse_planner import MuseSparkAttention
from bhashaflow_vision.session import VisionSession


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bhashaflow-demo")
    parser.add_argument(
        "--planner",
        choices=("fixture", "muse"),
        default="fixture",
        help="fixture (default, no network) or muse (muse-spark-1.3, needs a key)",
    )
    args = parser.parse_args(argv)
    if args.planner == "muse" and not muse_api_key():
        print("muse planner needs MODEL_API_KEY or BHASHAFLOW_MUSE_API_KEY", file=sys.stderr)
        return 2
    report = _build(args.planner).run()
    print(report.text())
    return 0 if report.ok else 1


def _build(planner_mode: str) -> DemoLoop:
    voice = StatusSynthesizer()
    if planner_mode == "muse":
        model = MuseSparkAttention(muse_api_key())
        planner = PlannerLoop(VisionSession.for_demo_script(model=model))
    else:
        planner = PlannerLoop(VisionSession.for_demo_script())
    pipeline = AudioPipeline(FixtureTranscriber(), voice)
    return DemoLoop(planner, FixtureActionEngine(), pipeline, voice)


if __name__ == "__main__":
    raise SystemExit(main())
