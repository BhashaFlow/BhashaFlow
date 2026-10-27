# Planner loop

This is the see-and-decide path for the stage script: Downloads, then a PDF or a sheet, then mail. The comparison for feel is ChatGPT Voice with computer use, whose observe step on a similar script often takes on the order of a second. The goal here is a short pause between the utterance and a click or type handoff. Speech recognition, speech synthesis, and the OS action itself sit outside this budget.

`PlannerLoop` in `bhashaflow-orchestrator` runs one utterance. CI uses the fixture heuristic. A live HTTP model is optional.

## Model

Default model: `FixtureAttention`. It scores the accessibility snapshot already attached to the fixture frame. One matching keyword clears the confidence gate. Two close scores abstain. There is no network call.

Optional model: set `BHASHAFLOW_VISION_ENDPOINT` to an `http://` or `https://` URL. `EndpointAttention` posts the prompt and the element names, roles, and hints. It does not post pixels. The response is `{"choice": "<element name>", "confidence": 0.0}` or `{"abstain": true}`. Transport errors become an empty score list, which vision reports as `low_confidence` with `recoverable=True`. CI leaves the variable empty.

## Prompt

Each ground uses this text (`bhashaflow_vision.prompts.build_prompt`):

```text
App: {app}
Elements: {comma-separated names, or (none)}
Task: choose one element to click or type. Abstain if two match.
Utterance: {last 40 whitespace tokens}
```

The header stays fixed. Only the utterance is truncated, and truncation keeps the tail, so a correction at the end of a rambling line survives. The same scene and utterance reuse a cached prompt, because the prompt lists element names rather than pixels. Each `step` grabs once so a scene change is visible, and the recovery ground reuses that frame. The fixture heuristic still scores the raw utterance. The cache and the prompt text are what the HTTP model and the overlay debug path share.

## Demo script

PDF path, four steps:

| Scene | Utterance | Handoff |
| --- | --- | --- |
| `downloads` | open report.pdf in Downloads | click `report.pdf` in Files |
| `pdf` | read the invoice total | click Invoice total in Preview |
| `mail` | focus the recipient | type the To field in Mail |
| `mail` | attach the file | click Attach in Mail |

Sheet branch, in place of the PDF step: scene `sheet`, utterance `select the total cell`, click Total in Sheets.

## Recovery

Vision already sets `low_confidence` and `recoverable=True` when the first ground abstains. The loop spends that signal once:

1. If the utterance has a trailing correction (` no `, ` actually `, or ` wait `), or it names exactly one candidate, ground a second time with that shorter text. The frame is not captured again.
2. A hit on that second ground is the handoff, with `recovered=True`.
3. A second miss clears `recoverable` so the caller does not retry forever.
4. If nothing sharper can be said, the loop returns the original recoverable failure and does not call the model again.

Example: `open budget.xlsx no open report.pdf` is ambiguous on the first pass and resolves to `report.pdf` on the recovery pass.

## Latency

Constants live in `bhashaflow_orchestrator.budget`. CI measures the fixture heuristic and fails if a step exceeds the ceiling. The ceilings are the demo-laptop estimate under the assumptions in that module.

| Slice | Budget |
| --- | --- |
| Planner step, frame already buffered, no recovery | 250 ms |
| Planner step that uses the one recovery | 450 ms |
| Four PDF-path steps back to back | 1000 ms |
| Extra estimate per HTTP ground | 400 ms, not asserted in CI |

Pointer mapping is inside the step budget (`POINTER_BUDGET_MS` is 5 ms). Capture stays on the existing 100 ms loop.
