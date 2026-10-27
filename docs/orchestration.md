# Orchestration loop

One process runs the canonical script by voice. The state machine is listen → ground → act → confirm → next, and stop aborts the session. CI uses fixture audio, fixture vision, and the fixture action engine. No API key is required.

## Entrypoint

```bash
uv run bhashaflow-demo
```

That plays wake (`bhashaflow start`), the four demo lines, and `stop`. It does not read the keyboard. The stage log goes to stdout. `ok=true` and `steps=4` on the `phase=done` line means the script finished.

`--planner muse` switches grounding to `muse-spark-1.3` and exits with status 2 when no Model API key is set. The default planner is the fixture heuristic, even if a key happens to be in the environment. `BHASHAFLOW_PLANNER=muse` is the same opt-in for `planner_attention_from_env()`.

## State machine

| Phase | What happens |
| --- | --- |
| `listen` | Local VAD closes an utterance and speech-to-text returns a line |
| `ground` | `PlannerLoop.step` maps the line to a click or type target. Indicator: `thinking` |
| `act` | The action engine opens or focuses the app when it changes, then clicks or types. Indicator: `acting` |
| `confirm` | A short line through the TTS interface. `focus_stolen=false` for the built-in backends |
| `next` | Ready for the following utterance |
| `abort` | The speaker said stop, abort, or cancel |
| `done` | The run finished. `steps`, `recoveries`, and `ok` are on this line |

A recoverable action failure confirms `Trying that again` and performs the same handoff once more. A second failure confirms `I could not do that` and counts as a failed step. Vision's own one-shot recovery still happens inside `PlannerLoop` and shows up as `recovered=true` on the ground line.

The log is one `key=value` line per event. Utterances with spaces are quoted. That is the stage debug log: target, app, ok, reason, attempts, and latency.

## Pluggable pieces

`DemoLoop` takes a planner, an action engine, an audio pipeline, and a synthesizer. `DemoLoop.for_fixture()` wires the offline stand-ins. Tracks can replace any one of them without changing the state machine.

| Concern | Fixture | Live opt-in |
| --- | --- | --- |
| Speech-to-text | Recorded clips | Muse Voice Transcribe when a key is set and the caller builds `MuseFileTranscriber` |
| Grounding | `FixtureAttention` | `muse-spark-1.3` chat completions, `reasoning_effort` `low` (never `none`) |
| Action | In-memory allowlist | `BHASHAFLOW_ACTIONS=desktop` |
| Confirmation | Local status | `beep` or an optional non-Muse command |
| Regions | Accessibility boxes on the fixture frame | `sam-3.1` when `BHASHAFLOW_SAM=1` and a key is set. Not used by this entrypoint |

`muse-wonder-1.0` is the long-horizon computer-use model. It is not this loop. The action package gates that path on the same allowlist.

## Script

| Scene | Utterance | Action |
| --- | --- | --- |
| `downloads` | open report.pdf in Downloads | click `report.pdf` in Files |
| `pdf` | read the invoice total | click Invoice total in Preview |
| `mail` | focus the recipient | type `demo@bhashaflow.test` |
| `mail` | attach the file | click Attach in Mail |

Wake and stop wrap those four lines in the fixture recording.
