"""Map a planner intent and the current frame to one UI target.

``FixtureAttention`` is the stand-in that CI and the stage-script fixtures use.
A live model implements ``AttentionModel`` and is passed to ``VisionSession``.
"""

import time
from typing import Protocol

from bhashaflow_vision.budget import GROUND_BUDGET_MS
from bhashaflow_vision.types import (
    Candidate,
    GroundingEvent,
    GroundingResult,
    GroundingStatus,
    ScreenFrame,
    UiElement,
)

MIN_CONFIDENCE = 0.6
MIN_MARGIN = 0.15
_HIT_BASE = 0.62
_EXTRA_HIT = 0.19
_MAX_CANDIDATES = 8


class AttentionModel(Protocol):
    """Score UI elements on one frame for one intent. Best candidate first."""

    def attend(self, frame: ScreenFrame, intent: str) -> tuple[tuple[UiElement, float], ...]:
        """Return ``(element, confidence)`` pairs, highest confidence first."""


class FixtureAttention:
    """Score the accessibility snapshot carried on a fixture frame.

    One matching keyword clears ``MIN_CONFIDENCE``. Further keyword hits raise
    the score. Two elements within ``MIN_MARGIN`` are treated as ambiguous.
    """

    def attend(self, frame: ScreenFrame, intent: str) -> tuple[tuple[UiElement, float], ...]:
        text = intent.casefold()
        scored = [(element, _keyword_confidence(text, element)) for element in frame.elements]
        scored.sort(key=lambda item: (-item[1], item[0].name))
        return tuple(scored)


def _keyword_confidence(intent: str, element: UiElement) -> float:
    hits = sum(1 for keyword in element.keywords if keyword.casefold() in intent)
    if hits == 0:
        return 0.0
    return min(1.0, _HIT_BASE + _EXTRA_HIT * (hits - 1))


def decide(
    frame: ScreenFrame | None,
    intent: str,
    model: AttentionModel,
    *,
    started: float | None = None,
) -> tuple[GroundingResult, tuple[Candidate, ...], ScreenFrame | None]:
    """Score ``intent`` against ``frame`` and apply the confidence gate."""
    start = time.perf_counter() if started is None else started
    if frame is None:
        result = _failure(
            frame_id=0,
            confidence=0.0,
            reason="no frame captured",
            latency_ms=_elapsed_ms(start),
        )
        return result, (), None

    ranking = model.attend(frame, intent.strip())
    candidates = tuple(
        Candidate(name=element.name, confidence=confidence)
        for element, confidence in ranking[:_MAX_CANDIDATES]
    )
    if not ranking or ranking[0][1] < MIN_CONFIDENCE:
        best = ranking[0][1] if ranking else 0.0
        reason = "no elements on frame" if not frame.elements else "low confidence"
        result = _failure(
            frame_id=frame.frame_id,
            confidence=best,
            reason=reason,
            latency_ms=_elapsed_ms(start),
        )
        return result, candidates, frame

    best_element, best_score = ranking[0]
    second = ranking[1][1] if len(ranking) > 1 else 0.0
    if best_score - second < MIN_MARGIN:
        result = _failure(
            frame_id=frame.frame_id,
            confidence=best_score,
            reason="ambiguous",
            latency_ms=_elapsed_ms(start),
        )
        return result, candidates, frame

    latency_ms = _elapsed_ms(start)
    result = GroundingResult(
        status=GroundingStatus.GROUNDED,
        frame_id=frame.frame_id,
        target=best_element,
        confidence=best_score,
        reason="",
        recoverable=False,
        latency_ms=latency_ms,
        within_budget=latency_ms <= GROUND_BUDGET_MS,
    )
    return result, candidates, frame


def event_for(
    intent: str,
    result: GroundingResult,
    frame: ScreenFrame | None,
    candidates: tuple[Candidate, ...],
) -> GroundingEvent:
    app = "" if frame is None else frame.app
    target = result.target
    if not app.strip() and target is not None and target.app.strip():
        app = target.app.strip()
    return GroundingEvent(
        intent=intent,
        scene_id="" if frame is None else frame.scene_id,
        app=app,
        frame_width=0 if frame is None else frame.width,
        frame_height=0 if frame is None else frame.height,
        result=result,
        candidates=candidates,
    )


def _failure(
    *,
    frame_id: int,
    confidence: float,
    reason: str,
    latency_ms: float,
) -> GroundingResult:
    return GroundingResult(
        status=GroundingStatus.LOW_CONFIDENCE,
        frame_id=frame_id,
        target=None,
        confidence=confidence,
        reason=reason,
        recoverable=True,
        latency_ms=latency_ms,
        within_budget=latency_ms <= GROUND_BUDGET_MS,
    )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0
