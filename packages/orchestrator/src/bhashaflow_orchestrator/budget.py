"""Latency ceilings for one planner step on a typical demo laptop.

Assumptions, not a stopwatch log from a single stage machine:

- The machine is a recent laptop. The model on the critical path is the
  in-process fixture heuristic, so there is no network round trip.
- The newest screen frame is already in the buffer. Capture stays on its
  100 ms loop and is not added again here.
- Speech recognition, speech synthesis, and the OS click or keypress are
  outside this budget. This is the see-and-decide pause a judge hears
  between the utterance and the handoff.
- ChatGPT Voice with computer use often spends on the order of a second on
  the observe step of a similar script. These ceilings keep one planning
  step, and one recovery, shorter than that pause.
- When ``BHASHAFLOW_VISION_ENDPOINT`` is set, add ``ENDPOINT_ESTIMATE_MS``
  per ground. That path is optional and is not what CI measures.
"""

from bhashaflow_vision.budget import GROUND_BUDGET_MS, VISION_STEP_BUDGET_MS

# In-process pointer mapping. Well under a frame time.
POINTER_BUDGET_MS = 5

# Frame already buffered, one ground, then the handoff. Vision's 200 ms step
# plus a margin for the prompt and the pointer map.
PLANNER_STEP_BUDGET_MS = VISION_STEP_BUDGET_MS + 50

# The one automatic re-ground, plus the same handoff margin.
PLANNER_RECOVERY_BUDGET_MS = VISION_STEP_BUDGET_MS + GROUND_BUDGET_MS + 100

# Four planning steps of the PDF path, back to back, heuristic model.
SCRIPT_PLAN_BUDGET_MS = 1000

# Extra estimate for one HTTP ground on a nearby endpoint. Not asserted in CI.
ENDPOINT_ESTIMATE_MS = 400
