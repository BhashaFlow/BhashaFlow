"""Retries and redaction used by the live Muse path."""

import pytest

from bhashaflow_shared.redact import redact_text
from bhashaflow_shared.retry import call_with_retries


def test_retry_repeats_retryable_errors_then_raises() -> None:
    calls = {"count": 0}
    pauses: list[int] = []

    def operation() -> str:
        calls["count"] += 1
        raise TimeoutError("slow")

    with pytest.raises(TimeoutError, match="slow"):
        call_with_retries(operation, retries=2, sleep=pauses.append)
    assert calls["count"] == 3
    assert pauses == [0, 1]


def test_retry_does_not_repeat_a_bad_response() -> None:
    calls = {"count": 0}

    def operation() -> str:
        calls["count"] += 1
        raise ValueError("not json")

    with pytest.raises(ValueError, match="not json"):
        call_with_retries(operation, retries=3, sleep=lambda _attempt: None)
    assert calls["count"] == 1


def test_retry_returns_the_first_success() -> None:
    calls = {"count": 0}

    def operation() -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise OSError("down")
        return "ok"

    assert call_with_retries(operation, retries=2, sleep=lambda _attempt: None) == "ok"
    assert calls["count"] == 2


def test_redact_hides_secrets_and_bearer_tokens() -> None:
    secret = "super-secret-key"
    text = f"failed for Bearer {secret} and again {secret}"
    redacted = redact_text(text, (secret, "tiny"))
    assert secret not in redacted
    assert "Bearer [redacted]" in redacted
    assert redacted.count("[redacted]") >= 2
