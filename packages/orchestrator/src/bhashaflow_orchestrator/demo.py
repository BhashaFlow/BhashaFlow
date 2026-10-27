"""Listen, ground, act, confirm, then take the next utterance.

The fixture path plays recorded audio. It does not read the keyboard. Vision
stays on ``FixtureAttention`` unless the caller passes another model. Action
stays on the fixture engine unless the caller passes another engine.
"""

from bhashaflow_action import DEMO_RECIPIENT, FixtureActionEngine, perform
from bhashaflow_action.desktop import DesktopActionEngine
from bhashaflow_action.engine import ActionResult
from bhashaflow_audio.control import classify_utterance, confirmation_for
from bhashaflow_audio.fixtures import CANONICAL_UTTERANCES, voice_script_clips
from bhashaflow_audio.pipeline import AudioPipeline
from bhashaflow_audio.sources import AudioSource, FixtureSource
from bhashaflow_audio.stt import FixtureTranscriber
from bhashaflow_audio.tts import SpeechSynthesis, StatusSynthesizer
from bhashaflow_audio.types import SpeechSegment
from bhashaflow_orchestrator.log import StageLog
from bhashaflow_orchestrator.loop import PlannerLoop, PlanStep
from bhashaflow_orchestrator.muse_planner import MusePlannerError
from bhashaflow_orchestrator.textutil import typed_text_from_utterance
from bhashaflow_vision import CaptureUnavailable
from bhashaflow_vision.session import VisionSession

# Scene on screen for each canonical line. Desktop capture has no scenes.
SCRIPT_SCENES = ("downloads", "pdf", "mail", "mail")


class DemoReport:
    """The outcome of one spoken run, plus the stage log."""

    def __init__(self, log: StageLog) -> None:
        self.log = log
        self.commands: list[str] = []
        self.confirmations: list[str] = []
        self.recoveries = 0
        self.failures = 0
        self.woke = False
        self.stopped = False
        self.ok = False

    def text(self) -> str:
        return self.log.text()


class DemoLoop:
    """The stage state machine. Interfaces are the constructor arguments."""

    def __init__(
        self,
        planner: PlannerLoop,
        actions: FixtureActionEngine | DesktopActionEngine,
        pipeline: AudioPipeline,
        tts: SpeechSynthesis,
        *,
        scenes: tuple[str, ...] = SCRIPT_SCENES,
        log: StageLog | None = None,
        require_script: bool = True,
    ) -> None:
        self._planner = planner
        self._actions = actions
        self._pipeline = pipeline
        self._tts = tts
        self._scenes = scenes
        self.log = StageLog() if log is None else log
        self._require_script = require_script

    @classmethod
    def for_fixture(
        cls,
        *,
        actions: FixtureActionEngine | None = None,
        fail_once: frozenset[str] = frozenset(),
        tts: SpeechSynthesis | None = None,
    ) -> "DemoLoop":
        """Offline script. Ignores API keys and vision endpoints."""
        voice = StatusSynthesizer() if tts is None else tts
        engine = FixtureActionEngine(fail_once=fail_once) if actions is None else actions
        return cls(
            PlannerLoop(VisionSession.for_demo_script()),
            engine,
            AudioPipeline(FixtureTranscriber(), voice),
            voice,
        )

    def run(self, source: AudioSource | None = None) -> DemoReport:
        """Run until the audio ends or the speaker says stop."""
        audio = FixtureSource(voice_script_clips()) if source is None else source
        report = DemoReport(self.log)
        armed = False
        index = 0
        stopped = False
        for pcm, sample_rate in audio.chunks():
            if stopped:
                break
            armed, index, stopped = self._consume(
                self._pipeline.feed(pcm, sample_rate),
                report,
                armed,
                index,
            )
        if not stopped:
            self._consume(self._pipeline.flush(), report, armed, index)
        if self._require_script:
            report.ok = (
                report.woke
                and report.stopped
                and report.commands == list(CANONICAL_UTTERANCES)
                and report.failures == 0
            )
        else:
            report.ok = report.woke and report.stopped and report.failures == 0
        self.log.event(
            phase="done",
            steps=len(report.commands),
            recoveries=report.recoveries,
            ok=report.ok,
        )
        return report

    def _consume(
        self,
        segments: list[SpeechSegment],
        report: DemoReport,
        armed: bool,
        index: int,
    ) -> tuple[bool, int, bool]:
        stopped = False
        for segment in segments:
            if not segment.transcript:
                if segment.error and segment.model != "fixture":
                    self.log.event(
                        phase="listen",
                        indicator="listening" if armed else "idle",
                        error=segment.error,
                        model=segment.model,
                    )
                continue
            armed, index, stopped = self._utterance(segment, report, armed, index)
            if stopped:
                break
        return armed, index, stopped

    def _utterance(
        self,
        segment: SpeechSegment,
        report: DemoReport,
        armed: bool,
        index: int,
    ) -> tuple[bool, int, bool]:
        kind = classify_utterance(segment.transcript, armed=armed)
        self.log.event(
            phase="listen",
            indicator="listening" if armed or kind == "wake" else "idle",
            utterance=segment.transcript,
            kind=kind,
        )
        if kind == "wake":
            report.woke = True
            self._confirm(report, "Listening", indicator="listening")
            return True, index, False
        if kind == "stop":
            report.stopped = True
            self._confirm(report, "Stopped", indicator="idle")
            self.log.event(phase="abort", indicator="idle", reason="stop")
            return False, index, True
        if kind != "command":
            return armed, index, False
        report.commands.append(segment.transcript)
        self._show(index)
        try:
            step = self._planner.step(segment.transcript)
        except MusePlannerError as exc:
            self.log.event(
                phase="ground",
                indicator="thinking",
                error=str(exc),
                model="muse-spark-1.3",
            )
            report.failures += 1
            self._confirm(report, "I could not do that", indicator="confirming")
            self.log.event(phase="next", indicator="listening")
            return True, index + 1, False
        target_name = "" if step.handoff.target is None else step.handoff.target.element_name
        self.log.event(
            phase="ground",
            indicator="thinking",
            target=target_name,
            attempts=step.attempts,
            recovered=step.recovered,
            latency_ms=round(step.latency_ms, 1),
        )
        result = self._act(step, report, retry=True, utterance=segment.transcript)
        if result.ok:
            self._confirm(report, confirmation_for(segment.transcript), indicator="confirming")
        else:
            report.failures += 1
            self._confirm(report, "I could not do that", indicator="confirming")
        self.log.event(phase="next", indicator="listening")
        return True, index + 1, False

    def _act(
        self,
        step: PlanStep,
        report: DemoReport,
        *,
        retry: bool,
        utterance: str,
    ) -> ActionResult:
        typed = self._typed(step, utterance)
        self.log.event(phase="act", indicator="acting", attempt="first")
        results = perform(self._actions, step.handoff, type_text=typed)
        result = results[-1]
        self._log_result(result)
        if result.ok or not result.recoverable or not retry or result.action == "none":
            return result
        report.recoveries += 1
        self._confirm(report, "Trying that again", indicator="confirming")
        self.log.event(phase="act", indicator="acting", attempt="retry")
        retried = perform(self._actions, step.handoff, type_text=typed)
        result = retried[-1]
        self._log_result(result)
        return result

    def _log_result(self, result: ActionResult) -> None:
        self.log.event(
            phase="act",
            indicator="acting",
            action=result.action,
            app=result.app,
            ok=result.ok,
            recoverable=result.recoverable,
            reason=result.reason,
            target=result.target_name,
        )

    def _confirm(self, report: DemoReport, text: str, *, indicator: str) -> None:
        spoken = self._tts.speak(text)
        report.confirmations.append(text)
        self.log.event(
            phase="confirm",
            indicator=indicator,
            text=text,
            focus_stolen=spoken.focus_stolen,
            backend=spoken.backend,
        )

    def _show(self, index: int) -> None:
        if index >= len(self._scenes):
            return
        try:
            self._planner.show(self._scenes[index])
        except CaptureUnavailable:
            self.log.event(phase="ground", scene=self._scenes[index], capture="desktop")

    def _typed(self, step: PlanStep, utterance: str) -> str:
        target = step.handoff.target
        if target is None or target.action != "type":
            return ""
        if self._require_script:
            return DEMO_RECIPIENT
        return typed_text_from_utterance(utterance)


def open_demo() -> DemoLoop:
    """Fixture demo. Live models are selected by the CLI, not by this helper."""
    return DemoLoop.for_fixture()
