"""Latency ceilings for the voice slice on a typical demo laptop.

Assumptions, not a stopwatch log from a single stage machine:

- Fixture VAD and fixture transcription run in-process. There is no network
  round trip, and CI measures this path.
- Live Muse file transcription adds ``MUSE_STT_ESTIMATE_MS``. That number is
  a planning estimate. CI does not call the network and does not assert it.
- Confirmations are a local status line or a short beep. The Meta Model API
  catalog has no text-to-speech model, so synthesis is outside Muse.
- Speech that arrives during a confirmation cancels it (barge-in). The local
  cancel itself is a few milliseconds; the feel of the cut-off depends on the
  playback device.
- ChatGPT Voice is the comparison for the whole turn. These slices stay short
  so the planner's step still fits in a pause that feels quick.
"""

# One energy frame. The decision budget covers a frame plus the bookkeeping.
VAD_FRAME_MS = 20
VAD_DECISION_BUDGET_MS = 30

# Trailing quiet after speech. This is the local end-of-utterance hangover.
# Muse realtime ENDPOINTING replaces it with the model's speechEnd event.
END_OF_UTTERANCE_MS = 400

# Fixture transcript lookup for one segment that VAD has already closed.
FIXTURE_STT_BUDGET_MS = 50

# Local confirmation. Status text or a beep. No window is opened.
TTS_CONFIRM_BUDGET_MS = 150

# Cancel a confirmation once local VAD sees speech onset.
BARGE_IN_BUDGET_MS = 100

# Planning estimate for one Muse file transcription. Not asserted in CI.
MUSE_STT_ESTIMATE_MS = 800

# Fixture clips and the WAV we build for file transcription.
SAMPLE_RATE_HZ = 16_000

# Engine-native rate for the realtime WebSocket. 16 kHz is accepted too.
MUSE_NATIVE_RATE_HZ = 24_000
