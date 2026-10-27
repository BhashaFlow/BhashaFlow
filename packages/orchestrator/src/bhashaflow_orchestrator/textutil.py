"""Text the live loop types. The fixture script keeps its own recipient."""

import re

from bhashaflow_action.engine import DEMO_RECIPIENT

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_QUOTED = re.compile(r'"([^"]+)"|\'([^\']+)\'')


def typed_text_from_utterance(utterance: str) -> str:
    """Pull an email, a quoted string, or the words after ``type``.

    ``focus the recipient`` stays the demo address so the stage line still
    types ``demo@bhashaflow.test``. Anything else that is not an obvious
    string returns empty, and the action engine refuses to type it.
    """
    text = utterance.strip()
    folded = text.casefold()
    if folded == "focus the recipient":
        return DEMO_RECIPIENT
    quoted = _QUOTED.search(text)
    if quoted is not None:
        return next(group for group in quoted.groups() if group)
    email = _EMAIL.search(text)
    if email is not None:
        return email.group(0)
    for prefix in ("type ", "enter ", "write "):
        if folded.startswith(prefix):
            return text[len(prefix) :].strip()
    return ""
