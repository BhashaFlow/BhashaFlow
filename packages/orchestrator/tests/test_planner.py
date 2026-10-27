import pytest

from bhashaflow_orchestrator import PlannerLoop, open_planner
from bhashaflow_orchestrator.budget import (
    ENDPOINT_ESTIMATE_MS,
    PLANNER_RECOVERY_BUDGET_MS,
    PLANNER_STEP_BUDGET_MS,
    SCRIPT_PLAN_BUDGET_MS,
)
from bhashaflow_vision.endpoint import EndpointAttention, attention_from_env
from bhashaflow_vision.grounding import FixtureAttention
from bhashaflow_vision.prompts import MAX_PROMPT_TOKENS, build_prompt, truncate_utterance
from bhashaflow_vision.session import VisionSession

PDF_PATH = (
    ("downloads", "open report.pdf in Downloads", "report.pdf", "click", "Files", False),
    ("pdf", "read the invoice total", "Invoice total", "click", "Preview", True),
    ("mail", "focus the recipient", "To", "type", "Mail", True),
    ("mail", "attach the file", "Attach", "click", "Mail", False),
)


def test_pdf_path_stays_inside_the_step_budget() -> None:
    planner = open_planner()
    spent = 0.0
    for scene, utterance, name, kind, app, focus_changed in PDF_PATH:
        planner.show(scene)
        step = planner.step(utterance)
        target = step.handoff.target
        assert target is not None
        assert target.element_name == name
        assert target.action == kind
        assert target.app == app
        assert step.handoff.focus_changed is focus_changed
        assert step.attempts == 1
        assert step.recovered is False
        assert step.within_budget
        assert step.latency_ms <= PLANNER_STEP_BUDGET_MS
        assert "Abstain if two match." in step.prompt
        spent += step.latency_ms
    assert spent <= SCRIPT_PLAN_BUDGET_MS
    assert len(PDF_PATH) == 4


def test_sheet_branch_maps_to_the_total_cell() -> None:
    planner = PlannerLoop(VisionSession.for_demo_script())
    planner.show("sheet")
    step = planner.step("select the total cell")
    assert step.handoff.target is not None
    assert step.handoff.target.element_name == "Total"
    assert step.handoff.target.action == "click"
    assert step.handoff.focus_app == "Sheets"
    assert step.within_budget


def test_correction_recovers_once_on_the_same_frame() -> None:
    planner = PlannerLoop(VisionSession.for_demo_script())
    planner.show("downloads")
    step = planner.step("open budget.xlsx no open report.pdf")
    assert step.attempts == 2
    assert step.recovered is True
    assert step.utterance_sent == "open report.pdf"
    assert step.handoff.target is not None
    assert step.handoff.target.element_name == "report.pdf"
    assert step.handoff.recoverable is False
    assert step.frame_id == 1
    assert step.handoff.target.frame_id == step.frame_id
    assert step.latency_ms <= PLANNER_RECOVERY_BUDGET_MS
    assert step.within_budget


def test_a_second_miss_is_not_recoverable() -> None:
    planner = PlannerLoop(VisionSession.for_demo_script())
    planner.show("downloads")
    step = planner.step("open report.pdf and budget.xlsx no open nothing")
    assert step.attempts == 2
    assert step.recovered is False
    assert step.handoff.target is None
    assert step.handoff.recoverable is False
    assert step.handoff.reason
    assert step.within_budget


def test_nonsense_returns_the_recoverable_failure() -> None:
    planner = PlannerLoop(VisionSession.for_demo_script())
    planner.show("downloads")
    step = planner.step("delete the system partition")
    assert step.attempts == 1
    assert step.recovered is False
    assert step.handoff.target is None
    assert step.handoff.recoverable is True
    assert step.handoff.reason == "low confidence"


def test_prompt_cache_hits_on_the_same_frame_and_utterance() -> None:
    planner = PlannerLoop(VisionSession.for_demo_script())
    planner.show("downloads")
    first = planner.step("open report.pdf in Downloads")
    second = planner.step("open report.pdf in Downloads")
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.prompt == second.prompt


def test_utterance_truncation_keeps_the_tail() -> None:
    words = [f"w{index}" for index in range(60)]
    words.append("report.pdf")
    text = truncate_utterance(" ".join(words))
    assert len(text.split()) == MAX_PROMPT_TOKENS
    assert text.endswith("report.pdf")
    prompt = build_prompt(None, " ".join(words))
    assert prompt.endswith("report.pdf")
    assert "Abstain if two match." in prompt


def test_endpoint_model_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BHASHAFLOW_VISION_ENDPOINT", raising=False)
    assert isinstance(attention_from_env(), FixtureAttention)
    monkeypatch.setenv("BHASHAFLOW_VISION_ENDPOINT", "file:///tmp/model")
    assert isinstance(attention_from_env(), FixtureAttention)
    monkeypatch.setenv("BHASHAFLOW_VISION_ENDPOINT", "https://vision.example/attend")
    model = attention_from_env()
    assert isinstance(model, EndpointAttention)

    session = VisionSession.for_demo_script()
    session.show("downloads")
    frame = session.tick()

    def transport(_url: str, _body: bytes, _timeout: float) -> dict[str, object]:
        return {"choice": "report.pdf", "confidence": 0.91}

    chosen = EndpointAttention("https://vision.example/attend", transport=transport).attend(
        frame,
        "open report.pdf",
    )
    assert chosen[0][0].name == "report.pdf"
    assert chosen[0][1] == pytest.approx(0.91)

    def broken(_url: str, _body: bytes, _timeout: float) -> dict[str, object]:
        raise OSError("endpoint down")

    missed = EndpointAttention("https://vision.example/attend", transport=broken)
    assert missed.attend(frame, "x") == ()
    assert ENDPOINT_ESTIMATE_MS == 400
