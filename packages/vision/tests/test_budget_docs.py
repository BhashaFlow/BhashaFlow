from pathlib import Path

from bhashaflow_vision import CAPTURE_INTERVAL_MS, GROUND_BUDGET_MS, VISION_STEP_BUDGET_MS


def test_readme_documents_the_vision_latency_budget() -> None:
    readme = Path(__file__).resolve().parents[3] / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert f"{CAPTURE_INTERVAL_MS} ms" in text
    assert f"{GROUND_BUDGET_MS} ms" in text
    assert f"{VISION_STEP_BUDGET_MS} ms" in text
    assert "ChatGPT Voice" in text
    assert "overlay_payload" in text
