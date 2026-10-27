import json

import pytest

from bhashaflow_orchestrator.muse_planner import (
    REASONING_EFFORT,
    SPARK_MODEL,
    MuseSparkAttention,
    planner_attention_from_env,
)
from bhashaflow_vision.grounding import FixtureAttention
from bhashaflow_vision.session import VisionSession


def test_spark_request_uses_the_tight_loop_model() -> None:
    captured: dict[str, object] = {}

    def transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["body"] = body
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "choices": [{"message": {"content": '{"choice": "report.pdf", "confidence": 0.91}'}}]
        }

    session = VisionSession.for_demo_script()
    session.show("downloads")
    frame = session.tick()
    chosen = MuseSparkAttention("test-key", transport=transport).attend(frame, "open report.pdf")
    assert chosen[0][0].name == "report.pdf"
    assert chosen[0][1] == pytest.approx(0.91)
    assert captured["url"] == "https://api.meta.ai/v1/chat/completions"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == "Bearer test-key"
    body = captured["body"]
    assert isinstance(body, bytes)
    payload = json.loads(body)
    assert payload["model"] == SPARK_MODEL
    assert payload["model"] == "muse-spark-1.3"
    assert payload["reasoning_effort"] == REASONING_EFFORT
    assert payload["reasoning_effort"] == "low"
    assert payload["reasoning_effort"] != "none"

    def broken(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        raise OSError("down")

    assert MuseSparkAttention("test-key", transport=broken).attend(frame, "open report.pdf") == ()


def test_muse_planner_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "live-key")
    monkeypatch.delenv("BHASHAFLOW_PLANNER", raising=False)
    assert isinstance(planner_attention_from_env(), FixtureAttention)
    monkeypatch.setenv("BHASHAFLOW_PLANNER", "muse")

    def transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        return {"choices": [{"message": {"content": '{"abstain": true}'}}]}

    model = planner_attention_from_env(transport=transport)
    assert isinstance(model, MuseSparkAttention)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert isinstance(planner_attention_from_env(transport=transport), FixtureAttention)
