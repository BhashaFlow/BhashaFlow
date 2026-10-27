"""Little-endian mono PCM helpers. No third-party audio library."""

import array
import io
import sys
import wave

from bhashaflow_audio.budget import SAMPLE_RATE_HZ


def pcm_tone(duration_ms: int, amplitude: int, sample_rate: int = SAMPLE_RATE_HZ) -> bytes:
    """Constant-amplitude int16 PCM. Zero amplitude is silence."""
    if duration_ms < 0:
        raise ValueError("duration must be non-negative")
    count = sample_rate * duration_ms // 1000
    samples = array.array("h", [amplitude] * count)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def pcm_from_le(pcm: bytes) -> array.array:
    """Decode signed 16-bit little-endian mono PCM."""
    if len(pcm) % 2:
        raise ValueError("pcm must be 16-bit")
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def pcm_to_le(samples: array.array) -> bytes:
    """Encode signed 16-bit samples as little-endian bytes."""
    copied = array.array("h", samples)
    if sys.byteorder != "little":
        copied.byteswap()
    return copied.tobytes()


def pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap mono 16-bit PCM in a RIFF/WAVE container Muse file transcription accepts."""
    if sample_rate not in (16_000, 24_000):
        raise ValueError("Muse file transcription expects 16 kHz or 24 kHz audio")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()
