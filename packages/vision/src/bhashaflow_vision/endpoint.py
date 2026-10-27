"""Optional HTTP attention model.

Used only when ``BHASHAFLOW_VISION_ENDPOINT`` is an http(s) URL. CI leaves the
variable empty and runs ``FixtureAttention``. Transport failures return no
elements so the planner sees a low-confidence, recoverable miss.
"""

import json
import os
import urllib.request
from collections.abc import Callable

from bhashaflow_vision.grounding import AttentionModel, FixtureAttention
from bhashaflow_vision.prompts import build_prompt
from bhashaflow_vision.types import ScreenFrame, UiElement

_ENV = "BHASHAFLOW_VISION_ENDPOINT"
Transport = Callable[[str, bytes, float], dict[str, object]]


class EndpointAttention:
    """Ask a remote model to name one element on the current frame.

    The request sends the prompt and the element names, roles, and hints. It
    does not send framebuffer pixels. The response is ``{"choice", "confidence"}``
    or ``{"abstain": true}``.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_s: float = 1.5,
        transport: Transport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self._timeout_s = timeout_s
        self._transport = _urllib_transport if transport is None else transport

    def attend(self, frame: ScreenFrame, intent: str) -> tuple[tuple[UiElement, float], ...]:
        body = json.dumps(
            {
                "prompt": build_prompt(frame, intent),
                "frame_id": frame.frame_id,
                "elements": [
                    {
                        "name": element.name,
                        "role": element.role,
                        "accessibility_hint": element.accessibility_hint,
                    }
                    for element in frame.elements
                ],
            }
        ).encode()
        try:
            parsed = self._transport(self.endpoint, body, self._timeout_s)
        except Exception:
            return ()
        if parsed.get("abstain") is True:
            return ()
        choice = str(parsed.get("choice", "")).casefold()
        raw_confidence = parsed.get("confidence", 0)
        if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, (int, float, str)):
            return ()
        try:
            confidence = float(raw_confidence)
        except ValueError:
            return ()
        confidence = min(1.0, max(0.0, confidence))
        for element in frame.elements:
            if element.name.casefold() == choice:
                return ((element, confidence),)
        return ()


def attention_from_env(fallback: AttentionModel | None = None) -> AttentionModel:
    """Return the endpoint model, or the fixture heuristic when the URL is unset."""
    endpoint = os.environ.get(_ENV, "").strip()
    if endpoint.startswith(("http://", "https://")):
        return EndpointAttention(endpoint)
    return FixtureAttention() if fallback is None else fallback


def _urllib_transport(url: str, body: bytes, timeout_s: float) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        parsed = json.loads(response.read().decode())
    if not isinstance(parsed, dict):
        raise ValueError("attention response must be a JSON object")
    return {str(key): value for key, value in parsed.items()}
