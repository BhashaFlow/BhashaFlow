"""Muse realtime socket. File transcription remains the stdlib path.

``connect_muse_realtime`` imports ``websocket-client`` only when a caller asks
for the socket. If that package is missing, or the socket does not open, the
error is ``RealtimeUnavailable``. Callers that asked for ``auto`` can use Muse
file transcription of the same model. They must not switch to the fixture catalog.
"""

import json
import queue
import threading
import time

from bhashaflow_audio.muse import MUSE_ASR_MODEL, CompletedTurn, MuseRealtimeSession, RealtimeSocket
from bhashaflow_audio.tts import SpeechSynthesis
from bhashaflow_audio.types import SpeechSegment


class RealtimeUnavailable(RuntimeError):
    """The realtime socket cannot be used. The message is safe to show."""


class WebsocketClientSocket:
    """Adapt ``websocket-client`` to the three methods ``MuseRealtimeSession`` uses."""

    def __init__(self, socket: object) -> None:
        self._socket = socket

    def send_text(self, data: str) -> None:
        send = getattr(self._socket, "send")
        send(data)

    def send_bytes(self, data: bytes) -> None:
        import websocket

        send = getattr(self._socket, "send")
        send(data, opcode=websocket.ABNF.OPCODE_BINARY)

    def recv(self) -> str | bytes | None:
        try:
            message = self._socket.recv()
        except Exception:
            return None
        if message == "":
            return None
        if isinstance(message, (str, bytes)):
            return message
        return None

    def close(self) -> None:
        closer = getattr(self._socket, "close", None)
        if closer is not None:
            closer()


def connect_muse_realtime(url: str, *, timeout_s: float) -> WebsocketClientSocket:
    """Open one session. Raises ``RealtimeUnavailable`` instead of a library error."""
    try:
        import websocket
    except ImportError as exc:
        raise RealtimeUnavailable(
            "websocket-client is not installed. "
            "Install it for Muse realtime, or set BHASHAFLOW_STT=file "
            "to use muse-voice-transcribe-1.0 file transcription."
        ) from exc
    try:
        socket = websocket.create_connection(url, timeout=timeout_s)
    except Exception as exc:
        raise RealtimeUnavailable(f"Muse realtime socket failed: {exc}") from exc
    return WebsocketClientSocket(socket)


class RealtimeUtterancePipeline:
    """Stream PCM and surface ``speechComplete`` as pipeline segments.

    A socket with ``recv_nowait`` is pumped on the caller thread, which is what
    tests use. A blocking socket is read on a background thread.
    """

    def __init__(
        self,
        socket: RealtimeSocket,
        session: MuseRealtimeSession,
        tts: SpeechSynthesis,
    ) -> None:
        self._socket = socket
        self._session = session
        self._tts = tts
        self.barge_ins = 0
        self._queue: queue.Queue[CompletedTurn | None] = queue.Queue()
        self._closed = False
        self._sync = hasattr(socket, "recv_nowait")
        self._thread: threading.Thread | None = None
        socket.send_text(json.dumps(session.handshake_payload()))
        if self._sync:
            self._pump()
        else:
            self._thread = threading.Thread(
                target=self._read_blocking,
                name="bhashaflow-muse-realtime",
                daemon=True,
            )
            self._thread.start()

    def feed(self, pcm: bytes, sample_rate: int) -> list[SpeechSegment]:
        self._barge(pcm)
        self._socket.send_bytes(pcm)
        if self._sync:
            self._pump()
        return self._drain(sample_rate)

    def flush(self) -> list[SpeechSegment]:
        try:
            self._socket.send_text(json.dumps({"type": "endStream"}))
        except Exception:
            return self._drain(self._session.sample_rate)
        if self._sync:
            self._pump()
            return self._drain(self._session.sample_rate)
        return self._drain(self._session.sample_rate, wait_s=0.5)

    def close(self) -> None:
        self._closed = True
        closer = getattr(self._socket, "close", None)
        if closer is not None:
            try:
                closer()
            except Exception:
                return
        if self._thread is not None:
            self._thread.join(timeout=1)

    def _read_blocking(self) -> None:
        while not self._closed:
            message = self._socket.recv()
            if message is None:
                self._queue.put(None)
                return
            self._ingest(message)

    def _pump(self) -> None:
        recv_nowait = getattr(self._socket, "recv_nowait", None)
        if recv_nowait is None:
            return
        while True:
            message = recv_nowait()
            if message is None:
                return
            self._ingest(message)

    def _ingest(self, message: object) -> None:
        if isinstance(message, bytes) or not isinstance(message, str):
            return
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        for turn in self._session.feed_event(event):
            self._queue.put(turn)

    def _drain(self, sample_rate: int, *, wait_s: float = 0.0) -> list[SpeechSegment]:
        segments: list[SpeechSegment] = []
        deadline = time.monotonic() + wait_s
        while True:
            try:
                if wait_s <= 0:
                    item = self._queue.get_nowait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return segments
                    item = self._queue.get(timeout=remaining)
            except queue.Empty:
                return segments
            if item is None:
                return segments
            segments.append(
                SpeechSegment(
                    transcript=item.text,
                    audio=b"",
                    sample_rate=sample_rate,
                    model=MUSE_ASR_MODEL,
                    stt_latency_ms=0.0,
                    vad_latency_ms=0.0,
                    end_of_utterance=item.endpointed,
                    error="",
                )
            )
            if wait_s <= 0:
                continue
            return segments

    def _barge(self, pcm: bytes) -> None:
        if not self._tts.is_speaking() or not _loud(pcm):
            return
        self._tts.cancel()
        self.barge_ins += 1


def _loud(pcm: bytes) -> bool:
    if len(pcm) < 2:
        return False
    for index in range(0, len(pcm) - 1, 2):
        sample = int.from_bytes(pcm[index : index + 2], "little", signed=True)
        if abs(sample) > 1000:
            return True
    return False
