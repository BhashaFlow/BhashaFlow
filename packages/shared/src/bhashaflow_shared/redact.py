"""Remove secrets from logs. Short strings are left alone so words survive."""

import re

_BEARER = re.compile(r"Bearer\s+\S+")
_MIN_SECRET = 8


def redact_text(text: str, secrets: tuple[str, ...]) -> str:
    """Replace configured secrets and bearer tokens with ``[redacted]``."""
    redacted = text
    for secret in secrets:
        if len(secret) < _MIN_SECRET:
            continue
        if secret in redacted:
            redacted = redacted.replace(secret, "[redacted]")
    return _BEARER.sub("Bearer [redacted]", redacted)
