"""Audio capture and speech track (Alucard).

Scaffolding only. No microphone, speech-to-text, or speech synthesis.
"""

from bhashaflow_shared import TRACKS

__version__ = "0.1.0"

TRACK = "audio"


def registered() -> bool:
    return TRACK in TRACKS
