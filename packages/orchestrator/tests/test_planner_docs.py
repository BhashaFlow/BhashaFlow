from pathlib import Path

from bhashaflow_orchestrator.budget import (
    PLANNER_RECOVERY_BUDGET_MS,
    PLANNER_STEP_BUDGET_MS,
    SCRIPT_PLAN_BUDGET_MS,
)
from bhashaflow_vision.budget import GROUND_BUDGET_MS, VISION_STEP_BUDGET_MS


def test_planner_doc_states_strategy_and_budgets() -> None:
    doc = Path(__file__).resolve().parents[3] / "docs" / "planner-loop.md"
    text = doc.read_text(encoding="utf-8")
    assert f"{PLANNER_STEP_BUDGET_MS} ms" in text
    assert f"{PLANNER_RECOVERY_BUDGET_MS} ms" in text
    assert f"{SCRIPT_PLAN_BUDGET_MS} ms" in text
    assert "Abstain if two match." in text
    assert "report.pdf" in text
    assert "Invoice total" in text
    assert "total cell" in text
    assert "Attach" in text
    assert "recoverable" in text
    assert "ChatGPT Voice" in text
    assert "moat" not in text.casefold()
    assert PLANNER_STEP_BUDGET_MS == 250
    assert PLANNER_RECOVERY_BUDGET_MS == 450
    assert PLANNER_STEP_BUDGET_MS > VISION_STEP_BUDGET_MS
    assert PLANNER_RECOVERY_BUDGET_MS >= PLANNER_STEP_BUDGET_MS + GROUND_BUDGET_MS
