"""Always-on voice control. Wake and stop are spoken. Indicators are text.

This is not a chat box. Nothing here reads the keyboard, and confirmations go
through the TTS interface, which does not focus a window. The action track
can replace the command handler; the default handler only marks ``acting``
and picks a short confirmation.
"""

from pathlib import Path

from bhashaflow_audio.fixtures import voice_script_clips
from bhashaflow_audio.pipeline import AudioPipeline
from bhashaflow_audio.sources import AudioSource, FixtureSource
from bhashaflow_audio.stt import FixtureTranscriber
from bhashaflow_audio.tts import SpeechSynthesis, StatusSynthesizer

_WAKE = frozenset({"bhashaflow", "bhashaflow start", "start", "start listening"})
_STOP = frozenset({"stop", "abort", "cancel", "bhashaflow stop", "stop listening"})

_CONFIRMATIONS = {
    "open report.pdf in downloads": "Opening report.pdf",
    "read the invoice total": "Reading the invoice",
    "focus the recipient": "Focusing the recipient",
    "attach the file": "Attaching the file",
}


class VoiceEvent:
    """One indicator change a stage display can show without taking focus."""

    def __init__(self, phase: str, indicator: str, text: str, *, focus_stolen: bool) -> None:
        self.phase = phase
        self.indicator = indicator
        self.text = text
        self.focus_stolen = focus_stolen


class VoiceRun:
    """What the control plane heard and said during one session."""

    def __init__(self) -> None:
        self.events: list[VoiceEvent] = []
        self.commands: list[str] = []
        self.confirmations: list[str] = []
        self.woke = False
        self.stopped = False
        self.indicator = "idle"

    def print(self) -> None:
        for event in self.events:
            print(f"indicator={event.indicator} text={event.text}")


class VoiceControl:
    """Wake, listen, and stop. Commands are ignored until the session is awake."""

    def __init__(
        self,
        tts: SpeechSynthesis | None = None,
        *,
        status_path: Path | str | None = None,
    ) -> None:
        self._tts = StatusSynthesizer() if tts is None else tts
        self._status_path = None if status_path is None else Path(status_path)
        self._armed = False
        self.indicator = "idle"
        self._pipeline = AudioPipeline(FixtureTranscriber(), self._tts)

    def run(self, source: AudioSource) -> VoiceRun:
        """Consume ``source`` until it ends or the speaker says stop."""
        result = VoiceRun()
        self._publish(result, "idle", "idle", "")
        for segment in self._pipeline.run(source):
            kind = _classify(segment.transcript, armed=self._armed)
            if kind == "wake":
                self._armed = True
                result.woke = True
                self._confirm(result, "wake", "listening", "Listening")
                continue
            if kind == "stop":
                self._armed = False
                result.stopped = True
                self._confirm(result, "stop", "idle", "Stopped")
                break
            if kind != "command":
                continue
            text = segment.transcript
            result.commands.append(text)
            self._publish(result, "listen", "listening", text)
            self._publish(result, "think", "thinking", text)
            self._publish(result, "act", "acting", text)
            phrase = confirmation_for(text)
            self._confirm(result, "confirm", "confirming", phrase)
            self._publish(result, "listen", "listening", "")
        result.indicator = self.indicator
        return result

    def _confirm(self, result: VoiceRun, phase: str, indicator: str, text: str) -> None:
        spoken = self._tts.speak(text)
        result.confirmations.append(text)
        self._publish(result, phase, indicator, text, focus_stolen=spoken.focus_stolen)

    def _publish(
        self,
        result: VoiceRun,
        phase: str,
        indicator: str,
        text: str,
        *,
        focus_stolen: bool = False,
    ) -> None:
        self.indicator = indicator
        result.events.append(VoiceEvent(phase, indicator, text, focus_stolen=focus_stolen))
        result.indicator = indicator
        if self._status_path is not None:
            self._status_path.parent.mkdir(parents=True, exist_ok=True)
            self._status_path.write_text(indicator + "\n", encoding="utf-8")


def confirmation_for(text: str) -> str:
    """A short line. Known demo commands get a specific phrase."""
    return _CONFIRMATIONS.get(text.casefold().strip(), "Heard you")


def run_spoken_demo() -> VoiceRun:
    """Play wake, the four demo lines, and stop. Does not read stdin."""
    return VoiceControl(StatusSynthesizer()).run(FixtureSource(voice_script_clips()))


def _classify(text: str, *, armed: bool) -> str:
    folded = text.casefold().strip()
    if folded in _STOP:
        return "stop"
    if folded in _WAKE:
        return "wake"
    if armed and folded:
        return "command"
    return "ignore"


def main() -> None:
    run_spoken_demo().print()


if __name__ == "__main__":
    main()
