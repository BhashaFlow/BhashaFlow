"""Retry Muse network calls. A bad response is not retried."""

import time
from collections.abc import Callable


def call_with_retries[T](
    operation: Callable[[], T],
    *,
    retries: int,
    sleep: Callable[[int], None] | None = None,
) -> T:
    """Call ``operation`` once, then up to ``retries`` more times after network errors.

    ``sleep`` receives the zero-based attempt that just failed. It is not called
    after the final failure. ``ValueError`` and other non-network errors propagate
    on the first attempt.
    """
    if retries < 0:
        raise ValueError("retries must be >= 0")
    pause = _default_sleep if sleep is None else sleep
    for attempt in range(retries + 1):
        try:
            return operation()
        except (OSError, TimeoutError):
            if attempt >= retries:
                raise
            pause(attempt)
    raise AssertionError("unreachable")


def _default_sleep(attempt: int) -> None:
    time.sleep(min(0.2, 0.02 * (2**attempt)))
