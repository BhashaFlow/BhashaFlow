"""Optional tight-loop grounding with Muse Spark.

``muse-spark-1.3`` chooses one element name when the frame already has an
accessibility list. A desktop frame with pixels and no elements asks the same
model for one allowlisted box. ``reasoning_effort`` is ``low``. The API rejects
``none``. This is not the long-horizon computer-use model; that path is
``muse-wonder-1.0`` and stays behind the action allowlist.

Selected only when ``BHASHAFLOW_PLANNER=muse`` and a Model API key is set.
Otherwise the fixture heuristic remains, including when a key is present but
the planner opt-in is not. Live mode constructs this model with ``strict``
so a transport failure is an error instead of an empty score list.
"""

import json
import os
from collections.abc import Callable
from dataclasses import replace

from bhashaflow_action.allowlist import DEMO_ALLOWLIST, canonical_app
from bhashaflow_audio.muse import muse_api_key
from bhashaflow_shared.retry import call_with_retries
from bhashaflow_vision.endpoint import attention_from_env
from bhashaflow_vision.grounding import AttentionModel
from bhashaflow_vision.png import frame_image
from bhashaflow_vision.prompts import build_prompt, truncate_utterance
from bhashaflow_vision.sam import SamRegion
from bhashaflow_vision.types import BoundingBox, ScreenFrame, UiElement

SPARK_MODEL = "muse-spark-1.3"
SPARK_URL = "https://api.meta.ai/v1/chat/completions"
REASONING_EFFORT = "low"

Transport = Callable[[str, bytes, dict[str, str], float], dict[str, object]]


class MusePlannerError(RuntimeError):
    """Spark could not be called. Live mode does not swap in the fixture model."""


class MuseSparkAttention:
    """Ask muse-spark-1.3 to name one element, or one allowlisted box."""

    model = SPARK_MODEL

    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport | None = None,
        url: str = SPARK_URL,
        timeout_s: float = 2.0,
        retries: int = 2,
        strict: bool = False,
        sleep: Callable[[int], None] | None = None,
    ) -> None:
        self._api_key = api_key
        self._transport = _urllib_transport if transport is None else transport
        self._url = url
        self._timeout_s = timeout_s
        self._retries = retries
        self._strict = strict
        self._sleep = sleep

    def attend(self, frame: ScreenFrame, intent: str) -> tuple[tuple[UiElement, float], ...]:
        if frame.elements:
            return self._attend_names(frame, intent)
        return self._attend_pixels(frame, intent)

    def _attend_names(self, frame: ScreenFrame, intent: str) -> tuple[tuple[UiElement, float], ...]:
        parsed = self._call(self._payload(frame, intent))
        if parsed is None:
            return ()
        choice = _choice(_message_content(parsed))
        if choice is None:
            return ()
        name, confidence, app = choice
        for element in frame.elements:
            if element.name.casefold() == name.casefold():
                if app and not element.app:
                    element = replace(element, app=app)
                return ((element, confidence),)
        return ()

    def _attend_pixels(
        self,
        frame: ScreenFrame,
        intent: str,
    ) -> tuple[tuple[UiElement, float], ...]:
        if frame.encoding != "rgb":
            if self._strict:
                raise MusePlannerError("muse-spark-1.3 needs an rgb desktop frame")
            return ()
        prepared = frame_image(frame.width, frame.height, frame.pixels)
        if prepared is None:
            if self._strict:
                raise MusePlannerError("desktop frame has no rgb pixels")
            return ()
        data_url, scale = prepared
        parsed = self._call(self._pixel_payload(intent, data_url))
        if parsed is None:
            return ()
        found = _pixel_element(_message_content(parsed), frame, scale)
        if found is None:
            return ()
        element, confidence = found
        return ((element, confidence),)

    def _call(self, payload: dict[str, object]) -> dict[str, object] | None:
        body = json.dumps(payload).encode()
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }

        def attempt() -> dict[str, object]:
            return self._transport(self._url, body, headers, self._timeout_s)

        try:
            return call_with_retries(attempt, retries=self._retries, sleep=self._sleep)
        except Exception as exc:
            if self._strict:
                raise MusePlannerError(f"muse-spark-1.3 request failed: {exc}") from exc
            return None

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

    def _pixel_payload(self, intent: str, data_url: str) -> dict[str, object]:
        allowlist = ", ".join(sorted(DEMO_ALLOWLIST))
        prompt = (
            f"Allowlist: {allowlist}.\n"
            "Reply with JSON "
            '{"app":"Files","action":"click","name":"report.pdf","x":0,"y":0,'
            '"width":10,"height":10,"confidence":0.9} '
            'or {"abstain": true}. '
            "action is click or type. Coordinates are pixels in the attached image. "
            "Use only an allowlisted app.\n"
            f"Utterance: {truncate_utterance(intent)}"
        )
        return {
            "model": self.model,
            "reasoning_effort": REASONING_EFFORT,
            "messages": [
                {
                    "role": "developer",
                    "content": (
                        "You are the tight computer-use loop. "
                        "Return one box on an allowlisted app. Do not leave the allowlist."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        }


class LiveSparkGrounder:
    """Spark, with optional sam-3.1 regions when the desktop frame has none.

    Region boxes are hints. If Spark does not pick one, the pixel request runs.
    Neither path substitutes the fixture heuristic.
    """

    def __init__(self, spark: MuseSparkAttention, sam: SamRegion | None = None) -> None:
        self._spark = spark
        self._sam = sam

    def attend(self, frame: ScreenFrame, intent: str) -> tuple[tuple[UiElement, float], ...]:
        if frame.elements:
            return self._spark.attend(frame, intent)
        proposed = self._regions(frame, intent)
        if proposed is not None and proposed.elements:
            ranked = self._spark.attend(proposed, intent)
            if ranked:
                return ranked
        return self._spark.attend(frame, intent)

    def _regions(self, frame: ScreenFrame, intent: str) -> ScreenFrame | None:
        if self._sam is None or frame.encoding != "rgb":
            return None
        prepared = frame_image(frame.width, frame.height, frame.pixels)
        if prepared is None:
            return None
        data_url, scale = prepared
        boxes = self._sam.boxes(intent, data_url)
        elements: list[UiElement] = []
        for index, (x, y, width, height) in enumerate(boxes, start=1):
            scaled = _scale_box(x, y, width, height, scale, frame.width, frame.height)
            if scaled is None:
                continue
            name = f"region-{index}"
            elements.append(
                UiElement(
                    name=name,
                    role="button",
                    bbox=BoundingBox(*scaled),
                    accessibility_hint=name,
                    keywords=(name,),
                )
            )
        if not elements:
            return None
        return replace(frame, elements=tuple(elements))


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


def _json_object(content: str) -> dict[str, object] | None:
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
    if not isinstance(parsed, dict):
        return None
    return {str(key): value for key, value in parsed.items()}


def _choice(content: str) -> tuple[str, float, str] | None:
    parsed = _json_object(content)
    if parsed is None or parsed.get("abstain") is True:
        return None
    name = parsed.get("choice")
    if not isinstance(name, str) or not name.strip():
        return None
    confidence = _confidence(parsed.get("confidence", 0.0))
    if confidence is None:
        return None
    app = parsed.get("app", "")
    if not isinstance(app, str):
        app = ""
    return name.strip(), confidence, canonical_app(app)


def _pixel_element(
    content: str,
    frame: ScreenFrame,
    scale: float,
) -> tuple[UiElement, float] | None:
    parsed = _json_object(content)
    if parsed is None or parsed.get("abstain") is True:
        return None
    app_raw = parsed.get("app")
    if not isinstance(app_raw, str):
        return None
    app = canonical_app(app_raw)
    if not app:
        return None
    name = parsed.get("name")
    if not isinstance(name, str) or not name.strip():
        label = "target"
    else:
        label = name.strip()
    action = parsed.get("action")
    role = "textbox" if action == "type" else "button"
    raw_box = []
    for key in ("x", "y", "width", "height"):
        number = _number(parsed.get(key))
        if number is None:
            return None
        raw_box.append(number)
    scaled = _scale_box(
        raw_box[0],
        raw_box[1],
        raw_box[2],
        raw_box[3],
        scale,
        frame.width,
        frame.height,
    )
    if scaled is None:
        return None
    confidence = _confidence(parsed.get("confidence", 0.9))
    if confidence is None:
        return None
    element = UiElement(
        name=label,
        role=role,
        bbox=BoundingBox(*scaled),
        accessibility_hint=label,
        keywords=(label,),
        app=app,
    )
    return element, confidence


def _scale_box(
    x: float,
    y: float,
    width: float,
    height: float,
    scale: float,
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int] | None:
    left = int(round(x * scale))
    top = int(round(y * scale))
    box_width = int(round(width * scale))
    box_height = int(round(height * scale))
    if box_width <= 0 or box_height <= 0 or left < 0 or top < 0:
        return None
    if left >= frame_width or top >= frame_height:
        return None
    if left + box_width > frame_width:
        box_width = frame_width - left
    if top + box_height > frame_height:
        box_height = frame_height - top
    if box_width <= 0 or box_height <= 0:
        return None
    return left, top, box_width, box_height


def _confidence(raw: object) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return min(1.0, max(0.0, float(raw)))


def _number(raw: object) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw)


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
