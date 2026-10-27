"""See, decide, and hand off one spoken step.

``PlannerLoop.step`` grounds the utterance, maps a hit to a click or type
target, and spends at most one recovery when vision marks the miss
recoverable. It does not send OS input.
"""

import time
from dataclasses import dataclass

from bhashaflow_action import FocusSession, PointerHandoff
from bhashaflow_orchestrator.budget import PLANNER_RECOVERY_BUDGET_MS, PLANNER_STEP_BUDGET_MS
from bhashaflow_vision import GroundingStatus
from bhashaflow_vision.endpoint import attention_from_env
from bhashaflow_vision.prompts import PromptCache, build_prompt, recovery_utterance
from bhashaflow_vision.session import VisionSession


@dataclass(frozen=True)
class PlanStep:
    """The handoff for one utterance, including whether recovery ran."""

    intent: str
    utterance_sent: str
    prompt: str
    attempts: int
    recovered: bool
    handoff: PointerHandoff
    latency_ms: float
    within_budget: bool
    frame_id: int
    cache_hit: bool


class PlannerLoop:
    """Run the demo script one utterance at a time."""

    def __init__(self, session: VisionSession, focus: FocusSession | None = None) -> None:
        self._session = session
        self._focus = FocusSession() if focus is None else focus
        self._cache = PromptCache()

    def show(self, scene_id: str) -> None:
        self._session.show(scene_id)

    def tick(self) -> None:
        self._session.tick()

    def step(self, intent: str) -> PlanStep:
        """Ground ``intent``. Re-ground once when a sharper clause exists."""
        started = time.perf_counter()
        # One grab for this step. Recovery grounds again on this same frame.
        self._session.tick()
        event = self._session.ground(intent)
        attempts = 1
        sent = intent.strip()
        prompt, cache_hit = self._remember(sent)
        if event.result.status is GroundingStatus.LOW_CONFIDENCE and event.result.recoverable:
            names = tuple(candidate.name for candidate in event.candidates)
            narrowed = recovery_utterance(intent, names)
            if narrowed and narrowed.casefold() != sent.casefold():
                sent = narrowed
                prompt, recovery_hit = self._remember(sent)
                cache_hit = cache_hit and recovery_hit
                event = self._session.ground(narrowed)
                attempts = 2
        handoff = self._focus.consume(event)
        recovered = attempts == 2 and handoff.target is not None
        if attempts == 2 and handoff.target is None:
            handoff.recoverable = False
        latency_ms = (time.perf_counter() - started) * 1000
        budget = PLANNER_RECOVERY_BUDGET_MS if attempts == 2 else PLANNER_STEP_BUDGET_MS
        frame = self._session.latest_frame()
        return PlanStep(
            intent=intent,
            utterance_sent=sent,
            prompt=prompt,
            attempts=attempts,
            recovered=recovered,
            handoff=handoff,
            latency_ms=latency_ms,
            within_budget=latency_ms <= budget,
            frame_id=0 if frame is None else frame.frame_id,
            cache_hit=cache_hit,
        )

    def _remember(self, utterance: str) -> tuple[str, bool]:
        frame = self._session.latest_frame()
        scene_id = "" if frame is None else frame.scene_id
        return self._cache.resolve(scene_id, utterance, lambda: build_prompt(frame, utterance))


def open_planner() -> PlannerLoop:
    """Fixture script, plus the HTTP model when the endpoint env var is set."""
    return PlannerLoop(VisionSession.for_demo_script(model=attention_from_env()))
