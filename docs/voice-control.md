# Voice control plane

The demo is driven by speech. There is no typed chat and no keyboard step in the fixture script. A judge says a wake phrase, the four demo lines, and stop.

## Wake and stop

The session starts idle and ignores commands. Any of these wakes it: `bhashaflow`, `bhashaflow start`, `start`, `start listening`. The confirmation is `Listening`.

Any of these stops it, including mid-script: `stop`, `abort`, `cancel`, `bhashaflow stop`, `stop listening`. The confirmation is `Stopped`. Later audio in the same recording is not treated as a command.

## Indicators

Each change is a text event. Nothing opens a window or steals focus from the desktop. A projector can tail the log. Set `BHASHAFLOW_STATUS_FILE` to a path and the current indicator is written there as one word.

| Indicator | When |
| --- | --- |
| `idle` | Before wake, and after stop |
| `listening` | Awake and waiting for the next utterance |
| `thinking` | A command was heard and is about to be handled |
| `acting` | The command handler is running. The default handler is a stub the action track replaces |
| `confirming` | A short confirmation is being handed to the TTS interface |

## Confirmations

Confirmations are short (40 characters or fewer) and go through the TTS interface from the audio pipeline. The default backend is local status, so the line is logged and no window is focused. Muse has no TTS model; see [audio-pipeline.md](audio-pipeline.md).

| Utterance | Confirmation |
| --- | --- |
| wake | Listening |
| open report.pdf in Downloads | Opening report.pdf |
| read the invoice total | Reading the invoice |
| focus the recipient | Focusing the recipient |
| attach the file | Attaching the file |
| stop | Stopped |

## Hands-off fixture run

No API key and no keyboard:

```bash
uv run python -m bhashaflow_audio.control
```

That plays the recorded wake, the four demo lines, and stop, and prints `indicator=...` lines. `run_spoken_demo()` is the same call.
