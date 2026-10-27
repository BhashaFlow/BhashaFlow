"""Latency budget for the vision slice of a spoken desktop turn.

ChatGPT Voice with computer use is the comparison for the same kind of script
(open a download, look at a PDF or sheet, continue in mail). That observe step
often takes on the order of a second before the following action. These numbers
are only the vision slice: capture runs beside the planner, and grounding uses
the newest frame already in the buffer. Audio, planning, and OS actions are
outside this budget.
"""

# Near-continuous capture. The planner polls the latest frame and does not wait
# for the next grab.
CAPTURE_INTERVAL_MS = 100

# Attention scoring against the current frame.
GROUND_BUDGET_MS = 150

# Grab already done, then ground. Keeps the vision slice well under a second
# so the rest of the turn can still feel quick next to Voice with computer use.
VISION_STEP_BUDGET_MS = 200
