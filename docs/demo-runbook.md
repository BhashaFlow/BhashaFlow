# Demo runbook

Rehearse the stage script on a laptop with no API key. The default command is fixture audio, fixture vision, and the fixture action engine. It does not read the keyboard, record the screen, or inject input. One click misses on purpose and the loop says `Trying that again`, then completes the script.

## Command

```bash
uv python install 3.12
uv sync --all-packages
uv run bhashaflow-demo
```

Expect a final line like:

```text
phase=done steps=4 recoveries=1 ok=true
```

And a confirmation `text="Trying that again"` before `Opening report.pdf`. `focus_stolen=false` on every confirmation. Muse has no TTS model, so the default backend is a status line, not a speaker and not a window.

Clean script, no rehearsed miss:

```bash
uv run bhashaflow-demo --no-recover
```

That prints `recoveries=0`.

## What the script does

Wake (`bhashaflow start`), then:

| Scene | Utterance | Action |
| --- | --- | --- |
| Files / Downloads | open report.pdf in Downloads | click `report.pdf` (the first try misses, the retry hits) |
| Preview | read the invoice total | click Invoice total |
| Mail | focus the recipient | type `demo@bhashaflow.test` |
| Mail | attach the file | click Attach |

Then say `stop`. The fixture recording includes that word. Apps outside Files, Preview, Sheets, and Mail are refused.

## Abort

- Say `stop`, `abort`, or `cancel`. The log shows `phase=abort reason=stop`.
- Press Ctrl-C. The process prints `phase=abort reason=keyboard` and exits 130.

Later audio after stop is ignored.

## Permissions

Grant these only to the demo process, and only for the mode you are about to run. Fixture mode needs none of them. Do not grant them to an editor or a shell that is only running `uv run pytest`.

| Permission | When | Where |
| --- | --- | --- |
| Microphone | `--mic` only | macOS Microphone, Windows microphone privacy, Linux portal |
| Screen recording | `--desktop` | macOS Screen Recording, Windows graphics capture, Linux portal or X11 |
| Accessibility | `BHASHAFLOW_ACTIONS=desktop` | macOS Accessibility, Windows UI Automation, Linux AT-SPI or the input helper (`xdotool`) |

`--desktop` by itself captures the screen and refuses OS commands until `BHASHAFLOW_ACTIONS=desktop` is set. The fixture heuristic cannot ground a desktop frame that has no accessibility elements, so the judged path is the fixture command above. Use `--desktop` only after the machine is showing the demo apps and you have decided to inject input.

`--mic` without `MODEL_API_KEY` exits 2 and does not open a device. Live speech-to-text is Muse Voice Transcribe (`muse-voice-transcribe-1.0`). The fixture command does not send the recorded tones to Muse, because they are not speech. The catalog is what makes the script reliable with no key.

## Environment

Copy `.env.example` to `.env` if you want a checklist. Nothing loads that file automatically. Export the variables you need.

| Variable | Empty / default | Set it to |
| --- | --- | --- |
| `MODEL_API_KEY` or `BHASHAFLOW_MUSE_API_KEY` | Fixture transcripts and fixture grounding | Live Muse. Also accepted: `BHASHAFLOW_STT_API_KEY` |
| `BHASHAFLOW_PLANNER` | Fixture heuristic | `muse` for `muse-spark-1.3` on the tight loop (`reasoning_effort` `low`). Needs a key. `--planner muse` is the same switch |
| `BHASHAFLOW_ACTIONS` | Fixture engine, no OS input | `desktop` to allow allowlisted OS commands |
| `BHASHAFLOW_CAPTURE` | Fixture scenes | `desktop` when you construct a session yourself. The CLI flag is `--desktop` |
| `BHASHAFLOW_SAM` | Off. Overlay keeps the accessibility box | `1` plus a key for optional `sam-3.1` region boxes |
| `BHASHAFLOW_TTS_BACKEND` | `status` (no audio, no window) | `beep`, or `command` with `BHASHAFLOW_TTS_COMMAND` (optional non-Muse) |
| `BHASHAFLOW_OVERLAY` | Draw instructions on | `0` to hide the debug panel |
| `BHASHAFLOW_STATUS_FILE` | Unset | A path. The voice plane writes one indicator word. It does not open a window |
| `BHASHAFLOW_VISION_ENDPOINT` | Fixture heuristic | An http(s) URL for the older endpoint model. Leave empty in CI |

`muse-wonder-1.0` is only the long-horizon computer-use path. The stage loop does not call it. Pending safety checks are not auto-acknowledged. The allowlist still applies.

## Warm-up

1. `uv sync --all-packages`
2. `uv run bhashaflow-demo --no-recover` and read `ok=true` `recoveries=0`
3. `uv run bhashaflow-demo` and read `ok=true` `recoveries=1` plus `Trying that again`
4. Say the abort phrase in your head against the log line `reason=stop` at the end of the recording
5. If you will use a key on stage, export it in the demo process only and run one `--planner muse` pass against fixture audio. If that call fails, fall back to the default command. Do not block the demo on TTS
6. If you will use the desktop, grant the permissions in the table, set `BHASHAFLOW_ACTIONS=desktop`, and run `--desktop` once before the room fills. Keep the fixture command as the backup

## Dry-run checklist

Initial these before the event. The fixture command is the backup if a live key or the desktop is not ready.

- [ ] ML (Lungile) — `uv run bhashaflow-demo` prints `steps=4` `recoveries=1` `ok=true`. Spark stays opt-in (`muse-spark-1.3`). SAM stays off unless a desktop region is needed (`sam-3.1`). Wonder is not on this loop.
- [ ] Audio (Alucard) — Wake, the four lines, and stop are in the log. Confirmations stay short and `focus_stolen=false`. Muse has no TTS model; the status backend is the plan.
- [ ] Arch (Satinder) — Files, Preview, and Mail are the apps that move. Terminal is not. The miss retries once. `stop` aborts. Desktop input stays off until `BHASHAFLOW_ACTIONS=desktop`.
