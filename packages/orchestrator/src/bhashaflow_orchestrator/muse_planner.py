"""Optional tight-loop grounding with Muse Spark.

``muse-spark-1.3`` chooses one element name. ``reasoning_effort`` is ``low``.
The API rejects ``none``. This is not the long-horizon computer-use model;
that path is ``muse-wonder-1.0`` and stays behind the action allowlist.

Selected only when ``BHASHAFLOW_PLANNER=muse`` and a Model API key is set.
Otherwise the fixture heuristic remains, including when a key is present but
the planner opt-in is not.
"""

import json
import os
from collections.abc import Callable

from bhashaflow_audio.muse import muse_api_key
from bhashaflow_vision.endpoint import attention_from_env
from bhashaflow_vision.grounding import AttentionModel
from bhashaflow_vision.prompts import build_prompt
from bhashaflow_vision.types import ScreenFrame, UiElement

SPARK_MODEL = "muse-spark-1.3"
SPARK_URL = "https://api.meta.ai/v1/chat/completions"
REASONING_EFFORT = "low"

Transport = Callable[[str, bytes, dict[str, str], float], dict[str, object]]


class MuseSparkAttention:
    """Ask muse-spark-1.3 to name one element. Transport failures abstain."""

    model = SPARK_MODEL

    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport | None = None,
        url: str = SPARK_URL,
        timeout_s: float = 2.0,
    ) -> None:
        self._api_key = api_key
        self._transport = _urllib_transport if transport is None else transport
        self._url = url
        self._timeout_s = timeout_s

    def attend(self, frame: ScreenFrame, intent: str) -> tuple[tuple[UiElement, float], ...]:
        body = json.dumps(self._payload(frame, intent)).encode()
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        try:
            parsed = self._transport(self._url, body, headers, self._timeout_s)
        except Exception:
            return ()
        content = _message_content(parsed)
        choice = _choice(content)
        if choice is None:
            return ()
        name, confidence = choice
        for element in frame.elements:
            if element.name.casefold() == name.casefold():
                return ((element, confidence),)
        return ()

    def _payload(self, frame: ScreenFrame, intent: str) -> dict[str, object]:
        return {
            "model": self.model,
            "reasoning_effort": REASONING_EFFORT,
            "messages": [
                {
                    "role": "developer",
                    "content": (
                        'Reply with JSON {"choice": "<element name>", "confidence": 0.9}. '
                        'If two elements match, reply {"abstain": true}.'
                    ),
                },
                {"role": "user", "content": build_prompt(frame, intent)},
            ],
        }


def planner_attention_from_env(transport: Transport | None = None) -> AttentionModel:
    """Fixture heuristic, unless the muse planner opt-in and a key are both set."""
    mode = os.environ.get("BHASHAFLOW_PLANNER", "").strip().casefold()
    key = muse_api_key()
    if mode == "muse" and key:
        return MuseSparkAttention(key, transport=transport)
    return attention_from_env()


def _message_content(parsed: dict[str, object]) -> str:
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _choice(content: str) -> tuple[str, float] | None:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.casefold().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or parsed.get("abstain") is True:
        return None
    name = parsed.get("choice")
    if not isinstance(name, str) or not name.strip():
        return None
    raw = parsed.get("confidence", 0.0)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    confidence = min(1.0, max(0.0, float(raw)))
    return name.strip(), confidence


def _urllib_transport(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, object]:
    import urllib.request

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parsed = json.loads(response.read().decode())
    if not isinstance(parsed, dict):
        raise ValueError("spark response must be a JSON object")
    return {str(key): value for key, value in parsed.items()}
