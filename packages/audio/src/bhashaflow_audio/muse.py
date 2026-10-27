"""Muse Voice Transcribe client.

File transcription uses ``POST https://api.meta.ai/v1/asr/transcribe``.
Realtime transcription uses ``wss://api.meta.ai/v1/asr/realtime``. Both run
``muse-voice-transcribe-1.0``. Realtime ``ENDPOINTING`` is the model's own
VAD: ``speechEnd`` is the boundary and ``speechComplete`` is the transcript.

The socket and the HTTP transport are injectable. Nothing in this module
opens a connection unless the caller supplies a transport or asks for the
default urllib transport.
"""

import json
import os
import time
import urllib.request
import uuid
from collections.abc import Callable, Iterable
from typing import Protocol

from bhashaflow_audio.pcm import pcm_to_wav
from bhashaflow_audio.types import Transcript

MUSE_ASR_MODEL = "muse-voice-transcribe-1.0"
MUSE_BASE_URL = "https://api.meta.ai/v1"
MUSE_REALTIME_URL = "wss://api.meta.ai/v1/asr/realtime"
MUSE_TRANSCRIBE_URL = f"{MUSE_BASE_URL}/asr/transcribe"

# Product words the demo script needs the model to keep intact.
DEMO_KEYWORDS = (
    "BhashaFlow",
    "report.pdf",
    "budget.xlsx",
    "Downloads",
    "invoice",
    "Attach",
    "recipient",
)

_KEY_ENVS = ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY")

Transport = Callable[[str, bytes, dict[str, str], float], dict[str, object]]


class CompletedTurn:
    """One Muse speech turn after native endpointing."""

    def __init__(self, text: str, endpointed: bool, turn_id: object) -> None:
        self.text = text
        self.endpointed = endpointed
        self.turn_id = turn_id


class RealtimeSocket(Protocol):
    """The slice of a WebSocket this session actually uses."""

    def send_text(self, data: str) -> None:
        """Send one JSON text frame."""

    def send_bytes(self, data: bytes) -> None:
        """Send one binary PCM frame."""

    def recv(self) -> str | bytes | None:
        """Return the next frame, or None when the server has closed."""


def muse_api_key() -> str:
    """Return the first configured Model API key, or an empty string."""
    for name in _KEY_ENVS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


class MuseFileTranscriber:
    """Transcribe one WAV clip with Muse Voice Transcribe."""

    model = MUSE_ASR_MODEL

    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport | None = None,
        url: str = MUSE_TRANSCRIBE_URL,
        timeout_s: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._transport = _urllib_transport if transport is None else transport
        self._url = url
        self._timeout_s = timeout_s

    def transcribe(self, audio: bytes, sample_rate: int) -> Transcript:
        """Post ``audio`` and return the transcript. Transport errors are empty text."""
        started = time.perf_counter()
        try:
            wav = pcm_to_wav(audio, sample_rate)
            body, content_type = _multipart(self._request_fields(), wav)
            headers = {
                "authorization": f"Bearer {self._api_key}",
                "accept": "application/json",
                "content-type": content_type,
            }
            parsed = self._transport(self._url, body, headers, self._timeout_s)
        except Exception as exc:
            return Transcript(
                text="",
                model=self.model,
                latency_ms=(time.perf_counter() - started) * 1000,
                endpointed=False,
                error=str(exc),
            )
        text = str(parsed.get("transcript", "") or "")
        turns = parsed.get("turns")
        endpointed = isinstance(turns, list) and len(turns) > 0
        return Transcript(
            text=text,
            model=self.model,
            latency_ms=(time.perf_counter() - started) * 1000,
            endpointed=endpointed or bool(text),
            error="",
        )

    def _request_fields(self) -> dict[str, object]:
        return {
            "model": self.model,
            "audioEncoding": "WAV",
            "mode": "ENDPOINTING",
            "languageBias": ["English"],
            "keywords": list(DEMO_KEYWORDS),
        }


class MuseRealtimeSession:
    """Speak the realtime protocol and read native endpointing events.

    ``run`` sends the handshake, binary PCM, and ``endStream``. Pass a socket.
    This class does not import a WebSocket library; file transcription is the
    stdlib live path, and a socket can be any object with the three methods.
    """

    def __init__(
        self,
        api_key: str,
        *,
        sample_rate: int = 16_000,
        session_id: str | None = None,
    ) -> None:
        if sample_rate not in (16_000, 24_000):
            raise ValueError("Muse realtime expects 16 kHz or 24 kHz PCM")
        self._api_key = api_key
        self.sample_rate = sample_rate
        self.session_id = session_id or f"bhashaflow-{uuid.uuid4()}"
        self.saw_speech_end = False
        self._partial = ""

    def handshake_payload(self) -> dict[str, object]:
        encoding = "PCM_24KHZ" if self.sample_rate == 24_000 else "PCM_16KHZ"
        return {
            "authorization": {"accessToken": f"Bearer {self._api_key}"},
            "audioEncoding": encoding,
            "model": MUSE_ASR_MODEL,
            "mode": "ENDPOINTING",
            "partialMode": "CUMULATIVE",
            "languageBias": ["English"],
            "keywords": list(DEMO_KEYWORDS),
        }

    def websocket_url(self) -> str:
        return f"{MUSE_REALTIME_URL}?sessionId={self.session_id}"

    def feed_event(self, event: dict[str, object]) -> list[CompletedTurn]:
        """Apply one server JSON frame. Unknown types are ignored."""
        kind = event.get("type")
        if not isinstance(kind, str):
            return []
        if kind == "transcript":
            self._partial = str(event.get("transcript", "") or "")
            return []
        if kind == "speechEnd":
            self.saw_speech_end = True
            return []
        if kind == "speechComplete":
            self.saw_speech_end = True
            text = str(event.get("transcript", "") or "")
            return [CompletedTurn(text, True, event.get("turnId"))]
        return []

    def run(self, socket: RealtimeSocket, pcm_chunks: Iterable[bytes]) -> list[CompletedTurn]:
        """Drive one session to completion. ``recv`` returns None at close."""
        socket.send_text(json.dumps(self.handshake_payload()))
        ack = socket.recv()
        if isinstance(ack, str):
            self.feed_event(json.loads(ack))
        for chunk in pcm_chunks:
            socket.send_bytes(chunk)
        socket.send_text(json.dumps({"type": "endStream"}))
        completed: list[CompletedTurn] = []
        while True:
            message = socket.recv()
            if message is None:
                break
            if isinstance(message, bytes):
                continue
            completed.extend(self.feed_event(json.loads(message)))
        return completed


def _multipart(fields: dict[str, object], wav: bytes) -> tuple[bytes, str]:
    boundary = f"bhashaflow{uuid.uuid4().hex}"
    request = json.dumps(fields).encode()
    chunks = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="request"\r\n',
        b"Content-Type: application/json\r\n\r\n",
        request,
        b"\r\n",
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="audio"; filename="utterance.wav"\r\n',
        b"Content-Type: audio/wav\r\n\r\n",
        wav,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _urllib_transport(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, object]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parsed = json.loads(response.read().decode())
    if not isinstance(parsed, dict):
        raise ValueError("transcription response must be a JSON object")
    return {str(key): value for key, value in parsed.items()}
