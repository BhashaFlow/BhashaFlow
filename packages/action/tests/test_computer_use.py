from bhashaflow_action.computer_use import (
    SPARK_TIGHT_LOOP_MODEL,
    WONDER_MODEL,
    gate_computer_call,
    parse_computer_call,
    wonder_request,
)


def test_wonder_is_the_long_horizon_model_and_safety_checks_block() -> None:
    body = wonder_request("attach the file", "data:image/png;base64,aaaa")
    assert body["model"] == WONDER_MODEL
    assert body["model"] == "muse-wonder-1.0"
    assert SPARK_TIGHT_LOOP_MODEL == "muse-spark-1.3"
    assert body["tools"] == [{"type": "computer"}]
    blocked = parse_computer_call(
        {
            "output": [
                {
                    "type": "computer_call",
                    "call_id": "call_1",
                    "actions": [{"type": "click", "button": "left", "x": 10, "y": 20}],
                    "pending_safety_checks": [
                        {"id": "csc_1", "code": "malicious_instructions", "message": "no"}
                    ],
                }
            ]
        }
    )
    assert blocked is not None
    gated = gate_computer_call(blocked, "Mail")
    assert gated is not None
    assert gated.ok is False
    assert gated.reason == "safety check pending"
    assert gate_computer_call(blocked, "Terminal") is not None
    assert gate_computer_call(blocked, "Terminal").reason == "app not on demo allowlist"

    clear = parse_computer_call(
        {
            "output": [
                {
                    "type": "computer_call",
                    "call_id": "call_2",
                    "actions": [{"type": "type", "text": "demo@bhashaflow.test"}],
                    "pending_safety_checks": [],
                }
            ]
        }
    )
    assert clear is not None
    assert gate_computer_call(clear, "Mail") is None
    assert clear.actions[0].kind == "type"
