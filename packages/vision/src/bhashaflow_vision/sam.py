"""Optional region grounding with SAM 3.1.

The fixture overlay already has accessibility boxes. SAM is for a desktop
frame when a noun phrase should propose a box. It is not called by the
fixture demo. Set ``BHASHAFLOW_SAM=1`` and a Model API key before using
``sam_from_env``. The request goes to ``POST /v1/responses`` with model
``sam-3.1``.
"""

import json
import os
from collections.abc import Callable

SAM_MODEL = "sam-3.1"
SAM_URL = "https://api.meta.ai/v1/responses"

Transport = Callable[[str, bytes, dict[str, str], float], dict[str, object]]


def sam_request(prompt: str, image_data_url: str) -> dict[str, object]:
    """One Responses API call that asks SAM for regions matching ``prompt``."""
    return {
        "model": SAM_MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url},
                ],
            }
        ],
    }


def parse_sam_boxes(payload: dict[str, object]) -> tuple[tuple[int, int, int, int], ...]:
    """Read ``x, y, width, height`` boxes. Unknown shapes yield an empty tuple."""
    found: list[tuple[int, int, int, int]] = []
    for box in _boxes(payload):
        parsed = _one_box(box)
        if parsed is not None:
            found.append(parsed)
    return tuple(found)


def sam_from_env(transport: Transport | None = None) -> "SamRegion | None":
    """Return a client only when ``BHASHAFLOW_SAM=1`` and a key is set."""
    flag = os.environ.get("BHASHAFLOW_SAM", "").strip()
    key = (
        os.environ.get("MODEL_API_KEY", "").strip()
        or os.environ.get("BHASHAFLOW_MUSE_API_KEY", "").strip()
    )
    if flag != "1" or not key:
        return None
    return SamRegion(key, transport=transport)


class SamRegion:
    """Post one prompt and image. Transport failures yield no boxes."""

    model = SAM_MODEL

    def __init__(self, api_key: str, *, transport: Transport | None = None) -> None:
        self._api_key = api_key
        self._transport = transport

    def boxes(self, prompt: str, image_data_url: str) -> tuple[tuple[int, int, int, int], ...]:
        if self._transport is None:
            return ()
        body = json.dumps(sam_request(prompt, image_data_url)).encode()
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        try:
            parsed = self._transport(SAM_URL, body, headers, 5.0)
        except Exception:
            return ()
        return parse_sam_boxes(parsed)


def _boxes(payload: object) -> list[object]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("boxes")
    if isinstance(raw, list):
        return raw
    output = payload.get("output")
    if isinstance(output, list):
        collected: list[object] = []
        for item in output:
            collected.extend(_boxes(item))
        return collected
    return []


def _one_box(box: object) -> tuple[int, int, int, int] | None:
    if not isinstance(box, dict):
        return None
    values = []
    for key in ("x", "y", "width", "height"):
        raw = box.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        values.append(int(raw))
    return values[0], values[1], values[2], values[3]
