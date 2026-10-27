"""Audio capture and speech track (Alucard).

Fixture clips flow through local VAD into a fixture transcript. Muse Voice
Transcribe is used only when a Model API key is set. Muse has no TTS model;
confirmations are a local status line, a beep, or an optional non-Muse command.
"""

from bhashaflow_audio.budget import (
    BARGE_IN_BUDGET_MS,
    END_OF_UTTERANCE_MS,
    FIXTURE_STT_BUDGET_MS,
    TTS_CONFIRM_BUDGET_MS,
    VAD_DECISION_BUDGET_MS,
)
from bhashaflow_audio.pipeline import AudioPipeline, transcribe_fixture, transcriber_from_env
from bhashaflow_shared import TRACKS

__version__ = "0.2.0"

TRACK = "audio"

__all__ = [
    "BARGE_IN_BUDGET_MS",
    "END_OF_UTTERANCE_MS",
    "FIXTURE_STT_BUDGET_MS",
    "TRACK",
    "TTS_CONFIRM_BUDGET_MS",
    "VAD_DECISION_BUDGET_MS",
    "AudioPipeline",
    "registered",
    "transcribe_fixture",
    "transcriber_from_env",
]


def registered() -> bool:
    return TRACK in TRACKS
