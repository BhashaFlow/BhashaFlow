"""Recorded stand-ins for the spoken demo script.

The bytes are tones, not a person's voice. Each line has its own amplitude so
the fixture transcriber can tell the clips apart without a model. Live Muse
receives the same bytes when a key is set.
"""

from bhashaflow_audio.budget import SAMPLE_RATE_HZ
from bhashaflow_audio.pcm import pcm_tone

# PDF path, in the order the planner already grounds. Wake and stop belong to
# the voice control plane, which wraps these lines.
CANONICAL_UTTERANCES = (
    "open report.pdf in Downloads",
    "read the invoice total",
    "focus the recipient",
    "attach the file",
)

WAKE_UTTERANCE = "bhashaflow start"
STOP_UTTERANCE = "stop"

# Spoken session controls. Included in the fixture catalog so wake and stop
# survive VAD as real utterances instead of being dropped as unknown audio.
CONTROL_UTTERANCES = (
    WAKE_UTTERANCE,
    "bhashaflow",
    "start",
    "start listening",
    STOP_UTTERANCE,
    "abort",
    "cancel",
    "bhashaflow stop",
    "stop listening",
)


class Clip:
    """One spoken line: loud frames, then enough silence to endpoint."""

    def __init__(self, transcript: str, speech: bytes, silence: bytes, sample_rate: int) -> None:
        self.transcript = transcript
        self.speech = speech
        self.silence = silence
        self.sample_rate = sample_rate


def amplitude_for(transcript: str) -> int:
    """A loud, stable amplitude unique to this line."""
    return 2500 + (sum(transcript.encode()) % 1500)


def make_clip(
    transcript: str,
    *,
    speech_ms: int = 200,
    silence_ms: int = 500,
    amplitude: int | None = None,
    sample_rate: int = SAMPLE_RATE_HZ,
) -> Clip:
    loud = amplitude_for(transcript) if amplitude is None else amplitude
    return Clip(
        transcript,
        pcm_tone(speech_ms, loud, sample_rate),
        pcm_tone(silence_ms, 0, sample_rate),
        sample_rate,
    )


def noise_clip(
    *,
    duration_ms: int = 1000,
    amplitude: int = 80,
    sample_rate: int = SAMPLE_RATE_HZ,
) -> bytes:
    """Quiet room noise. Under the default energy gate."""
    return pcm_tone(duration_ms, amplitude, sample_rate)


def canonical_clips() -> tuple[Clip, ...]:
    """The four demo lines, each followed by endpointing silence."""
    return tuple(make_clip(text) for text in CANONICAL_UTTERANCES)


def voice_script_clips() -> tuple[Clip, ...]:
    """Wake, the four demo lines, then stop. No keyboard input is required."""
    lines = (WAKE_UTTERANCE, *CANONICAL_UTTERANCES, STOP_UTTERANCE)
    return tuple(make_clip(text) for text in lines)
