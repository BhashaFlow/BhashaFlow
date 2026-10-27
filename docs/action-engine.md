# OS action engine

The action track turns a grounded pointer handoff into click, type, focus, and open-app. The default engine records those steps in memory. It does not move the pointer. CI uses that engine.

## Allowlist

There is no unscoped control of the machine. Every primitive checks the app first and refuses anything else with `recoverable=false` and reason `app not on demo allowlist`. The runner, when there is one, is not called.

| App | Role in the script |
| --- | --- |
| Files | Downloads, including `report.pdf` and `budget.xlsx` |
| Preview | The open PDF |
| Sheets | The spreadsheet branch |
| Mail | Recipient and Attach |

`Terminal`, browsers, and any other name are out. An empty app name is out.

Text is capped at 200 characters and rejected when it contains a control character, including newlines. That keeps a typed recipient from becoming a script.

## Primitives

| Primitive | Success | Failure |
| --- | --- | --- |
| `open_app` | Front app becomes the allowlisted app | Off-list app, or the desktop command exits non-zero |
| `focus` | Front app is recorded or activated | Same as open |
| `click` | The element name is recorded at the handoff point | Off-list, or a rehearsed `click missed` |
| `type` | The text is recorded on the element | Empty text, text too long, control characters, off-list |

`perform(engine, handoff, type_text=...)` opens and focuses when the front app differs, then clicks or types. A low-confidence handoff (no target) returns one failure and copies `recoverable` from vision so the loop can retry once. A rehearsed miss (`fail_once={"click:report.pdf"}`) fails the first click with `recoverable=true` and `reason="click missed"`, then succeeds. A second miss is up to the caller; the engine spends the failure once.

The PDF path drives Files, Preview, and Mail. That is more than the two apps the stage script has to show.

## Desktop mode

`BHASHAFLOW_ACTIONS=desktop` selects `DesktopActionEngine`. Any other value, including unset, stays on the fixture engine.

| OS | Open | Click / type |
| --- | --- | --- |
| macOS | `open -a` with Finder, Preview, Numbers, or Mail | System Events via `osascript`. Needs Accessibility |
| Linux | `xdg-open` best effort | `xdotool` best effort. Needs an input interface such as AT-SPI or X11 |
| Windows | `start` | A real click via `SetCursorPos` and `mouse_event`, and typing via `SendKeys`. Needs permission to inject input |

Grant Accessibility (macOS), UI Automation (Windows), or the input portal (Linux) only to the demo process. Do not grant them to a shell that is only running tests. Fixture mode needs none of these.

## Computer use

The Meta computer-use guide runs the long-horizon observe-act loop on `muse-wonder-1.0` (`POST /v1/responses`, tool `computer`). `wonder_request` builds that body. `parse_computer_call` reads a `computer_call`. `gate_computer_call` returns a failure when the front app is off the allowlist or `pending_safety_checks` is non-empty. Safety checks are not auto-acknowledged.

The tight per-utterance loop does not call Wonder. That loop stays on the fixture planner, or on `muse-spark-1.3` when the spark opt-in is on. Wonder is the long-horizon path the computer-use guide names, and it still cannot leave the allowlist.
