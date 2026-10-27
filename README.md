# BhashaFlow

BhashaFlow is a hackathon project for a voice-first desktop demo. You speak a task, and three tracks — vision, audio, and action — are coordinated by an orchestrator so the demo can listen, look at the screen, and carry the task out on the machine. ChatGPT Voice with computer use already pairs speech with computer control, and Claude is the typed-assistant comparison. This repository is the shared workspace for one continuous spoken desktop session over a short build. Action and the orchestrator are still placeholders. The audio package turns fixture clips (or a microphone) into end-of-utterance transcripts. The vision package publishes screen frames and grounds the demo script through a fixture attention model.

## Stack

Python 3.12 and [uv](https://docs.astral.sh/uv/) 0.13.5. The stack is still open past this baseline. Python is the default glue because the vision, audio, and orchestration tracks can share one runtime, one lockfile, and one CI job while the demo is built. A desktop shell and specific models can land later without rearranging the packages.

Runtime pins:

- Python `3.12` in [`.python-version`](.python-version) and `requires-python = ">=3.12,<3.13"`
- uv `0.13.5` in the root `pyproject.toml` (`tool.uv.required-version`) and in CI
- Third-party tools (pytest, ruff, hatchling, mss) in the committed [`uv.lock`](uv.lock)

## Layout

| Path | Track | What lands here |
| --- | --- | --- |
| `packages/vision` | Lungile | Screen capture and UI grounding |
| `packages/audio` | Alucard | Capture, speech-to-text, speech synthesis |
| `packages/action` | Satinder | Pointer handoff for clicks and typing. No OS input yet. |
| `packages/orchestrator` | Satinder | Coordination of the other tracks |
| `packages/shared` | All | Identifiers shared by the tracks |

The root project is a uv workspace (`tool.uv.package = false`) that depends on `bhashaflow-orchestrator`. Each directory under `packages/` is its own installable package. `uv sync` installs them editable into `.venv`.

## Run locally

Install uv 0.13.5, then sync the workspace. Tests are the runnable surface until a demo entrypoint exists. The audio fixture path prints the four demo lines with no API key:

```bash
uv run python -m bhashaflow_audio
```

```bash
curl -LsSf https://astral.sh/uv/0.13.5/install.sh | sh
uv python install 3.12
uv sync --all-packages
cp .env.example .env
uv run pytest
```

`.env` is gitignored. Nothing loads that file automatically. `open_session()` reads `BHASHAFLOW_CAPTURE` from the process environment when you export it.

## CI locally

The GitHub Actions job [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pull requests and on pushes to `main`. Reproduce it with:

```bash
uv python install 3.12
uv sync --frozen --all-packages
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

`uv sync --frozen` fails if `uv.lock` is out of date. After changing dependencies, run `uv lock` and commit the lockfile.

## Vision

`bhashaflow-vision` keeps a near-continuous frame available for a planner and grounds one intent onto a single UI element (bounding box, accessibility hint, and confidence). CI uses `BHASHAFLOW_CAPTURE=fixture`, which replays Downloads → PDF or sheet → mail with no desktop. `BHASHAFLOW_CAPTURE=desktop` grabs the primary monitor through [mss](https://github.com/BoboTiG/python-mss) and needs screen-recording permission on the demo machine. Tests probe that adapter and accept a missing monitor, so Linux CI does not need a display.

`FixtureAttention` scores the accessibility snapshot on the current fixture frame. That is the stand-in for a live attention model: implement `AttentionModel` and pass it to `VisionSession` when pixel grounding is ready. Until then, a desktop frame with no elements returns `low_confidence` and `recoverable=True`, which is the signal orchestration uses to retry once. This package does not send OS input. `VisionSession.overlay_payload()` is the debug hook the stage overlay reads (last status, target, candidates, and timing). `GroundingOverlay` turns that payload into draw instructions. It does not open a window, so CI can check placement without a display.

### Click and type targets

`FocusSession.consume(event)` maps a grounded event to a `PointerTarget`. The action package re-exports that type from `bhashaflow_action` so the action engine has one import. A click target is the center of the bounding box plus a stable accessibility id, `{app}:{accessibility_hint}`. Text fields (`textbox` and similar roles) are type targets at that same point. The id does not include the frame number, so the same control stays the same target across frames.

Low-confidence events copy `recoverable` and `reason` from vision and set no point. `FocusSession` treats the app on the frame as window focus. The first app is not a change. A later frame from another app sets `focus_changed` (Files to Preview or Sheets, then Mail). Staying inside Files does not.

### Stage overlay

`GroundingOverlay.render(session.overlay_payload())` builds a side panel for the projector: the app, the selected element in 36 px accent type, and `CLICK` or `TYPE` in 28 px. Colors are light or amber on `#0E1116`. The panel prefers the right edge and moves to the left if that would cover the target. The element is marked with four bars outside its box, so the click point is not painted. `toggle()` or `BHASHAFLOW_OVERLAY=0` clears the instructions for debugging. A low-confidence payload shows that status and whether it is recoverable, and draws no target.

### Latency budget

ChatGPT Voice with computer use is the comparison for this script. Its observe step often takes on the order of a second. The numbers below are only the vision slice, so the rest of a turn still has room to feel quick. Capture runs beside the planner; grounding uses the newest frame already in the buffer. Constants live in `bhashaflow_vision.budget`.

| Slice | Budget |
| --- | --- |
| Capture interval | 100 ms (about 10 Hz), off the planner's critical path |
| Grounding | 150 ms |
| Vision step, frame already buffered | 200 ms |
| Planner step, no recovery | 250 ms |
| Planner step with the one recovery | 450 ms |

### Planner loop

`PlannerLoop` in `bhashaflow-orchestrator` grounds one utterance, maps it to a click or type target, and re-grounds once when vision returns a recoverable miss and the utterance has a sharper clause. The model, the prompt (including the 40-token tail truncation), and the latency assumptions are in [docs/planner-loop.md](docs/planner-loop.md). CI runs the fixture heuristic. `BHASHAFLOW_VISION_ENDPOINT` selects an HTTP model when it is an http(s) URL; leave it empty for local and CI runs. The loop does not send OS input.

### Planner use

```python
from bhashaflow_vision import open_session

session = open_session()  # fixture unless BHASHAFLOW_CAPTURE=desktop
session.start()
event = session.ground("open report.pdf in Downloads")
payload = session.overlay_payload()
session.stop()
```

`event.result.status` is `grounded` or `low_confidence`. A grounded target includes `bbox` (`x`, `y`, `width`, `height` in that frame), `accessibility_hint`, and `confidence` in `[0, 1]`. A low-confidence result has no target.

| Scene | App | Example intent | Target |
| --- | --- | --- | --- |
| `downloads` | Files | open report.pdf in Downloads | `report.pdf` |
| `downloads` | Files | open the spreadsheet in Downloads | `budget.xlsx` |
| `pdf` | Preview | read the invoice total | Invoice total |
| `sheet` | Sheets | select the total cell | Total |
| `mail` | Mail | attach the file | Attach |

`session.show("pdf")` changes the fixture scene. Call `tick` or leave `start` running so the planner sees the new frame.

## Audio

`bhashaflow-audio` segments a stream and transcribes each closed utterance. CI plays tones that stand in for the demo script (`FixtureSource` + `EnergyVad` + `FixtureTranscriber`). A microphone is the same path with a frame reader. `open_microphone()` needs the optional `sounddevice` package and OS microphone permission; CI never calls it.

Live speech-to-text is Muse Voice Transcribe, `muse-voice-transcribe-1.0`. Set `MODEL_API_KEY` (or `BHASHAFLOW_MUSE_API_KEY`, or `BHASHAFLOW_STT_API_KEY`) to post clips to `https://api.meta.ai/v1/asr/transcribe`. The realtime socket is `wss://api.meta.ai/v1/asr/realtime` in `ENDPOINTING` mode, which is the model's own VAD (`speechEnd` closes the utterance, `speechComplete` carries the text). With no key, nothing touches the network.

Muse has no TTS model. Confirmations use `BHASHAFLOW_TTS_BACKEND`: `status` (default, log only), `beep` (local tone), or `command` (optional non-Muse executable via `BHASHAFLOW_TTS_COMMAND`). None of the built-in backends focus a window. Details and the latency table are in [docs/audio-pipeline.md](docs/audio-pipeline.md).

| Slice | Budget |
| --- | --- |
| VAD decision | 30 ms |
| End of utterance (trailing silence) | 400 ms |
| Fixture transcription, segment already closed | 50 ms |
| Local confirmation | 150 ms |
| Barge-in cancel | 100 ms |

Quiet ambient noise stays under the energy gate. Speech during a held confirmation cancels it (barge-in, best effort).

## Voice control

The control plane is voice-first. It stays idle until it hears `bhashaflow start` (or `bhashaflow`, `start`, `start listening`). It then accepts the demo lines and stops on `stop`, `abort`, or `cancel`. Indicators are the words `listening`, `thinking`, `acting`, and `confirming`. They are log lines, and an optional `BHASHAFLOW_STATUS_FILE`, not a window. Confirmations are short status lines through the TTS interface, so the desktop keeps focus.

```bash
uv run python -m bhashaflow_audio.control
```

That recording is wake, the four demo lines, and stop. It does not read the keyboard. The acting step is a stub until the action track is wired. Details are in [docs/voice-control.md](docs/voice-control.md).

## OS permissions

Fixture capture, tests, and CI do not record the screen, read the microphone, or inject input. Desktop capture needs screen recording on the demo machine. Clicking and typing are not implemented; the action track will need accessibility access when it lands.

- **Microphone** — voice input for the audio track.
- **Screen recording** — desktop capture. On macOS this is Screen Recording. On Windows it is graphics capture. On Linux it is a portal (or X11 capture) under Wayland or X11.
- **Accessibility** — future OS actions. On macOS this is Accessibility. On Windows it is UI Automation. On Linux it is an input and assistive-technology interface such as AT-SPI.

Grant those only to the demo process, in System Settings (macOS), Privacy settings (Windows), or the desktop portal (Linux). Do not grant them to editors or shells that are only running tests.

## Environment

Placeholders live in [`.env.example`](.env.example):

- `BHASHAFLOW_LOG_LEVEL` — future process log level (`info` by default)
- `BHASHAFLOW_CAPTURE` — `fixture` (default) or `desktop`
- `BHASHAFLOW_OVERLAY` — `1` (default) draws the side panel, `0` hides it
- `MODEL_API_KEY`, `BHASHAFLOW_MUSE_API_KEY`, or `BHASHAFLOW_STT_API_KEY` — Muse Voice Transcribe. Empty keeps the fixture transcript catalog.
- `BHASHAFLOW_TTS_BACKEND` — `status` (default), `beep`, or `command`. Muse has no TTS model.
- `BHASHAFLOW_TTS_COMMAND` — optional non-Muse executable when the backend is `command`
- `BHASHAFLOW_TTS_API_KEY` — unused. Kept so older notes still have a name for a future non-Muse TTS key.
- `BHASHAFLOW_VISION_ENDPOINT` — optional http(s) attention model; empty uses the fixture heuristic

Leave keys empty until the track that reads them exists. Do not commit real credentials.

## Issues

Track work in [GitHub issues](https://github.com/BhashaFlow/BhashaFlow/issues).
