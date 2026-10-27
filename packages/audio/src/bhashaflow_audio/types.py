"""Speech values shared by VAD, transcription, and synthesis."""


class Transcript:
    """Text for one closed utterance."""

    def __init__(
        self,
        *,
        text: str,
        model: str,
        latency_ms: float,
        endpointed: bool,
        error: str = "",
    ) -> None:
        self.text = text
        self.model = model
        self.latency_ms = latency_ms
        self.endpointed = endpointed
        self.error = error


class SpeechSegment:
    """One utterance the pipeline is ready to hand to the control plane."""

    def __init__(
        self,
        *,
        transcript: str,
        audio: bytes,
        sample_rate: int,
        model: str,
        stt_latency_ms: float,
        vad_latency_ms: float,
        end_of_utterance: bool,
        error: str = "",
    ) -> None:
        self.transcript = transcript
        self.audio = audio
        self.sample_rate = sample_rate
        self.model = model
        self.stt_latency_ms = stt_latency_ms
        self.vad_latency_ms = vad_latency_ms
        self.end_of_utterance = end_of_utterance
        self.error = error


class SynthesisResult:
    """What a confirmation did. Built-in backends never focus a window."""

    def __init__(
        self,
        *,
        text: str,
        backend: str,
        played: bool,
        focus_stolen: bool,
        cancelled: bool,
        latency_ms: float,
    ) -> None:
        self.text = text
        self.backend = backend
        self.played = played
        self.focus_stolen = focus_stolen
        self.cancelled = cancelled
        self.latency_ms = latency_ms
