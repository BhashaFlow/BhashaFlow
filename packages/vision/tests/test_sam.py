import json

import pytest

from bhashaflow_vision.sam import SAM_MODEL, parse_sam_boxes, sam_from_env, sam_request


def test_sam_request_names_the_region_model(monkeypatch: pytest.MonkeyPatch) -> None:
    body = sam_request("report.pdf", "data:image/png;base64,aaaa")
    assert body["model"] == SAM_MODEL
    assert body["model"] == "sam-3.1"
    boxes = parse_sam_boxes({"boxes": [{"x": 48, "y": 160, "width": 320, "height": 40}]})
    assert boxes == ((48, 160, 320, 40),)
    nested = {"output": [{"boxes": [{"x": 1, "y": 2, "width": 3, "height": 4}]}]}
    assert parse_sam_boxes(nested) == ((1, 2, 3, 4),)

    monkeypatch.delenv("BHASHAFLOW_SAM", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "live-key")
    assert sam_from_env() is None
    monkeypatch.setenv("BHASHAFLOW_SAM", "1")
    captured: dict[str, object] = {}

    def transport(
        url: str,
        body_bytes: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["body"] = body_bytes
        return {"boxes": [{"x": 8, "y": 9, "width": 10, "height": 11}]}

    client = sam_from_env(transport=transport)
    assert client is not None
    assert client.boxes("report.pdf", "data:image/png;base64,aaaa") == ((8, 9, 10, 11),)
    raw = captured["body"]
    assert isinstance(raw, bytes)
    assert json.loads(raw)["model"] == "sam-3.1"
    assert captured["url"] == "https://api.meta.ai/v1/responses"
