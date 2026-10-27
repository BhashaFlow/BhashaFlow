"""Prompt text for one grounding step.

The fixture heuristic does not read this string. It scores the raw utterance.
An HTTP model receives ``build_prompt`` so the instruction, the element list,
and the utterance stay in one place. The utterance is truncated to the last
``MAX_PROMPT_TOKENS`` whitespace tokens so a long, noisy aside cannot crowd
out the correction at the end.
"""

from collections.abc import Callable

from bhashaflow_vision.types import ScreenFrame

MAX_PROMPT_TOKENS = 40
_CORRECTIONS = (" no ", " actually ", " wait ")


class PromptCache:
    """Reuse a prompt for the same scene and utterance."""

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self._store: dict[tuple[str, str], str] = {}

    def resolve(
        self,
        scene_id: str,
        utterance: str,
        build: Callable[[], str],
    ) -> tuple[str, bool]:
        key = (scene_id, utterance.strip())
        cached = self._store.get(key)
        if cached is not None:
            self.hits += 1
            return cached, True
        prompt = build()
        self._store[key] = prompt
        self.misses += 1
        return prompt, False


def truncate_utterance(utterance: str, limit: int = MAX_PROMPT_TOKENS) -> str:
    tokens = utterance.split()
    if len(tokens) <= limit:
        return " ".join(tokens)
    return " ".join(tokens[-limit:])


def build_prompt(frame: ScreenFrame | None, utterance: str) -> str:
    """Fixed header plus a truncated utterance. Element names are the allow-list."""
    app = "" if frame is None else frame.app
    names = () if frame is None else tuple(element.name for element in frame.elements)
    listed = ", ".join(names) if names else "(none)"
    return (
        f"App: {app}\n"
        f"Elements: {listed}\n"
        "Task: choose one element to click or type. Abstain if two match.\n"
        f"Utterance: {truncate_utterance(utterance)}"
    )


def recovery_utterance(intent: str, candidate_names: tuple[str, ...]) -> str:
    """Narrow a miss to one clause, or to the single named candidate.

    An empty string means there is nothing sharper to re-ground. Callers then
    keep the original recoverable failure instead of spending a second pass.
    """
    lowered = intent.casefold()
    padded = f" {lowered} "
    cut_at = -1
    for marker in _CORRECTIONS:
        idx = padded.rfind(marker)
        if idx > cut_at:
            cut_at = idx + len(marker)
    if cut_at > 0:
        narrowed = intent[cut_at - 1 :].strip()
        if narrowed and narrowed.casefold() != intent.strip().casefold():
            return narrowed
    mentioned = [name for name in candidate_names if name.casefold() in lowered]
    if len(mentioned) == 1:
        return mentioned[0]
    return ""
