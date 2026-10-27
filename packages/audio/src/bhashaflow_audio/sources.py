"""Audio sources. Fixture clips are the default. A mic is an injected reader."""

from collections.abc import Callable, Iterator

from bhashaflow_audio.budget import SAMPLE_RATE_HZ
from bhashaflow_audio.fixtures import Clip


class AudioSource:
    """Yields ``(pcm, sample_rate)`` until the stream ends."""

    def chunks(self) -> Iterator[tuple[bytes, int]]:
        raise NotImplementedError


class FixtureSource(AudioSource):
    """Play recorded clips: loud frames, then the silence that endpoints them."""

    def __init__(self, clips: tuple[Clip, ...]) -> None:
        self.clips = clips

    def chunks(self) -> Iterator[tuple[bytes, int]]:
        for clip in self.clips:
            yield clip.speech, clip.sample_rate
            yield clip.silence, clip.sample_rate


class MicrophoneUnavailable(RuntimeError):
    """No live microphone reader is available in this process."""


class MicrophoneSource(AudioSource):
    """Read int16 frames from ``reader`` until it returns empty bytes.

    CI passes a reader over fixture PCM. A hardware mic is the same interface:
    ``reader`` returns the next frame. This class does not open a device on
    import, and it does not request microphone permission by itself.
    """

    def __init__(self, reader: Callable[[], bytes], *, sample_rate: int = SAMPLE_RATE_HZ) -> None:
        self._reader = reader
        self.sample_rate = sample_rate

    def chunks(self) -> Iterator[tuple[bytes, int]]:
        while True:
            frame = self._reader()
            if not frame:
                return
            yield frame, self.sample_rate


def open_microphone(sample_rate: int = SAMPLE_RATE_HZ) -> MicrophoneSource:
    """Open the default input device when ``sounddevice`` is installed.

    The fixture source is what CI and the offline demo use. Call this only
    from a process that already has microphone permission.
    """
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise MicrophoneUnavailable(
            "No microphone backend is installed. Use FixtureSource, or pass a "
            "reader of int16 PCM frames to MicrophoneSource. A live mic needs "
            "the optional sounddevice package and OS microphone permission."
        ) from exc

    def reader() -> bytes:
        frames = int(sample_rate * 0.02)
        captured, _overflow = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        return captured.tobytes()

    return MicrophoneSource(reader, sample_rate=sample_rate)


def microphone_status() -> tuple[bool, str]:
    """Report whether an input device can be queried. Does not start a recording."""
    try:
        import sounddevice as sd
    except ImportError:
        return False, (
            "No microphone backend. Install PortAudio and the optional sounddevice "
            "package (uv pip install sounddevice), then grant microphone permission "
            "to this process. Live mode will not switch to fixture audio."
        )
    try:
        device = sd.query_devices(kind="input")
    except Exception as exc:
        return False, (
            "No microphone is available ("
            + str(exc)
            + "). Grant microphone permission. Live mode will not switch to fixture audio."
        )
    name = "input"
    if isinstance(device, dict):
        raw = device.get("name", "input")
        if isinstance(raw, str) and raw.strip():
            name = raw.strip()
    return True, f"microphone reported: {name}"
