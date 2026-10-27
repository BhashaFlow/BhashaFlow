# Single-user desktop agent

This is the furthest BhashaFlow can run on one person's machine. It is a local agent with a Muse key and OS permissions. It is not a hosted product.

```bash
uv python install 3.12
uv sync --all-packages
cp .env.example .env
# Put a real key in MODEL_API_KEY. Do not commit .env.
uv run bhashaflow
```

`uv run bhashaflow-demo --live` is the same process. `uv run bhashaflow --fixture` and `uv run bhashaflow-demo` are the keyless rehearsal. Live mode does not switch to that rehearsal when a key, a device, or a helper is missing. It exits 2 and prints what to fix.

`bhashaflow` and `bhashaflow-demo --live` load `.env` from the working directory, or the file in `BHASHAFLOW_ENV_FILE`. Variables already exported win. The rehearsal commands do not load `.env`.

## What a person can do

With `MODEL_API_KEY` (or `BHASHAFLOW_MUSE_API_KEY` or `BHASHAFLOW_STT_API_KEY`), a microphone, screen recording, and an input helper:

1. Say `bhashaflow start` (or `bhashaflow`, `start`, `start listening`).
2. Speak an English command. The process transcribes it with `muse-voice-transcribe-1.0`, grounds it with `muse-spark-1.3` (`reasoning_effort` `low`), and runs click, type, focus, or open on **Files, Preview, Sheets, or Mail**.
3. Hear or read a short confirmation. Muse has no TTS model. The default is a status line. `beep` is a local tone. `command` is an optional non-Muse program named by `BHASHAFLOW_TTS_COMMAND`.
4. A failed allowlisted click or type is tried once more (`Trying that again`). A second failure stops that command.
5. Say `stop`, `abort`, or `cancel`, or press Ctrl-C (`phase=abort reason=keyboard`, exit 130).

Stdout is the stage log (`listen`, `ground`, `act`, `confirm`). Stderr is one JSON object per event. The API key is not written. Set `BHASHAFLOW_LOG_LEVEL` to `debug`, `info`, `warning`, or `error`.

Speech-to-text tries the realtime socket `wss://api.meta.ai/v1/asr/realtime` when `BHASHAFLOW_STT` is `auto` (the live default) or `realtime`. `auto` uses Muse file transcription (`POST https://api.meta.ai/v1/asr/transcribe`) if the socket cannot be opened, and the startup log says why. `realtime` exits 2 instead of switching. `file` skips the socket. Both transports are `muse-voice-transcribe-1.0`. Neither is the fixture catalog.

Grounding sends the screenshot to `muse-spark-1.3` and asks for one box on an allowlisted app. `Finder` is treated as Files and `Numbers` as Sheets. Any other app, including Terminal, is refused and the OS command is not run. Optional `sam-3.1` region boxes run only when `BHASHAFLOW_SAM=1`. `muse-wonder-1.0` is the long-horizon computer-use model. This loop does not call it. Pending safety checks are not auto-acknowledged.

Muse HTTP calls use `BHASHAFLOW_MUSE_TIMEOUT_S` (default 8 seconds) and `BHASHAFLOW_MUSE_RETRIES` extra attempts after the first (default 2). A Spark transport failure is logged and is not replaced with the fixture planner.

## Permissions

Grant these to the `bhashaflow` process only. Do not grant them to a shell that is only running `uv run pytest`. The preflight checks that a monitor, an input device, and the helper binary exist. It does not click. A missing Accessibility or input permission shows up as a failed action, which is retried once.

| Permission | Why | Where |
| --- | --- | --- |
| Microphone | Live speech. Needs the optional `sounddevice` package and PortAudio (`uv pip install sounddevice`) | macOS Microphone, Windows microphone privacy, Linux portal |
| Screen recording | The frame Spark sees | macOS Screen Recording, Windows graphics capture, Linux portal or X11 |
| Accessibility / input | Allowlisted click, type, focus, and open when `BHASHAFLOW_ACTIONS=desktop` | macOS Accessibility (`osascript`), Windows UI input (`powershell`), Linux `xdotool` and `xdg-open` |

| OS | Open / focus | Click | Type |
| --- | --- | --- | --- |
| macOS | `open -a` Finder, Preview, Numbers, or Mail, then activate | System Events click | System Events keystroke |
| Linux | `xdg-open` with the allowlisted name (best effort; the desktop file may not match) | `xdotool` move and click | `xdotool type` |
| Windows | `start` with the same logical name (Finder and Numbers are not Windows apps) | `SetCursorPos` and `mouse_event` | `SendKeys` |

Install `xdotool` and `xdg-open` on Linux before the first live run. The allowlist is still Files, Preview, Sheets, and Mail.

## Warm-up

1. `uv sync --all-packages`
2. `uv run bhashaflow-demo --no-recover` and read `ok=true` `recoveries=0`
3. `uv run bhashaflow-demo` and read `ok=true` `recoveries=1` plus `Trying that again`
4. Export `MODEL_API_KEY` in this process only
5. `uv run bhashaflow`. If it exits 2, the message names the missing key, helper, or permission. Fix that and run it again. Do not point the live command at the fixture rehearsal
6. Say the wake phrase, one command, then `stop`. Ctrl-C aborts if the phrase is not heard

## Abort

- `stop`, `abort`, or `cancel` logs `phase=abort reason=stop`
- Ctrl-C logs `phase=abort reason=keyboard` and exits 130

Speech after stop is ignored.

## Known gaps

This slice is not production-grade.

- No multi-tenant SaaS, billing, org admin, or cloud-hosted computer use for someone else's machine
- No App Store or signed installer. The entrypoint is `uv run bhashaflow`
- No full security audit. The allowlist is the boundary the process enforces. A wrong box inside Files, Preview, Sheets, or Mail can still be clicked
- No African-language model. Speech bias is English
- Muse has no TTS. Confirmations are status text, a local beep with no speaker device opened by this process, or an optional non-Muse command
- Desktop frames have no accessibility tree. Spark has to return coordinates. If the chat API rejects the image, the call fails loudly
- `muse-wonder-1.0` is implemented only as a gated request builder. The live loop does not run that computer-use session
- Preflight cannot prove macOS Accessibility or the Linux input portal was granted
- Windows open uses the macOS app names and often will not launch a local Files or Mail app
- The microphone package is optional so CI stays free of PortAudio
- There is no account, no remote kill switch, and no review UI beyond the stage log
