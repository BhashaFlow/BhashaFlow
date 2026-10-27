# Audio pipeline

Spoken input for the stage script: a microphone or a recorded fixture, local voice activity detection, then speech-to-text. Short confirmations go out through a separate synthesis interface. CI runs the fixture path and does not call the network.

## Models

Speech-to-text is Muse Voice Transcribe, `muse-voice-transcribe-1.0`, on the Meta Model API (`https://api.meta.ai/v1`).

| Path | When it runs | Endpoint |
| --- | --- | --- |
| Fixture catalog | No API key. This is CI and the offline demo. | In-process lookup of the recorded clips |
| File transcription | `MODEL_API_KEY`, `BHASHAFLOW_MUSE_API_KEY`, or `BHASHAFLOW_STT_API_KEY` is set | `POST https://api.meta.ai/v1/asr/transcribe` |
| Realtime | A caller supplies a WebSocket and a key | `wss://api.meta.ai/v1/asr/realtime` |

The file request is multipart: a JSON `request` part (`model`, `audioEncoding: WAV`, `mode: ENDPOINTING`, `languageBias: ["English"]`, demo `keywords`) and a mono 16-bit WAV at 16 kHz or 24 kHz. The realtime handshake sends the key in `authorization.accessToken` as `Bearer <key>`. The HTTP `Authorization` header is not used on the socket. Mode is `ENDPOINTING`, so the model does its own VAD.

Native endpointing events:

| Event | Meaning |
| --- | --- |
| `speechStart` | The model heard speech begin |
| `transcript` | A partial hypothesis. Cumulative mode replaces the previous partial |
| `speechEnd` | End of utterance. Not the transcript |
| `speechComplete` | The transcript for that `turnId` |

`MuseRealtimeSession` speaks that protocol against any socket with `send_text`, `send_bytes`, and `recv`. File transcription uses the standard library when no transport is injected. `connect_muse_realtime` opens that socket with `websocket-client` when a live session asks for it. Muse HTTP calls retry transient network errors (`BHASHAFLOW_MUSE_RETRIES`, default 2 extra attempts) and time out (`BHASHAFLOW_MUSE_TIMEOUT_S`). A failed live call is reported. It is not replaced with the fixture catalog.

English is the demo language (`languageBias: English`). The model can recognize other languages; the stage script does not depend on that.

## Local VAD

`EnergyVad` is the offline end-of-utterance detector. A couple of loud 20 ms frames open speech. `400 ms` of trailing quiet closes the utterance. Quiet ambient noise stays under the gate and does not open a segment. The noise floor adapts only while the frame is already under the base threshold, so a quiet room does not swallow the next command. Loud noise can still open a segment. That is a best-effort energy detector, not a speech model.

On the realtime socket, ignore the local hangover and wait for `speechEnd` / `speechComplete`.

## Barge-in

If a confirmation is still held as speaking and local VAD sees speech onset, the pipeline cancels the synthesizer and keeps the new utterance. That cancel is barge-in. It is local. Playback that has already reached a speaker cannot be pulled back.

## TTS gap

Muse has no TTS model in the Model API catalog. Confirmations use a pluggable interface and do not block the demo:

| `BHASHAFLOW_TTS_BACKEND` | Behavior |
| --- | --- |
| unset or `status` | Record the line. Nothing is played. No window is opened. |
| `beep` | A short local tone via a sink callback. No window. |
| `command` | Optional non-Muse process. Also set `BHASHAFLOW_TTS_COMMAND` to the executable. The argument is the confirmation text. Leave this unset in CI. The command should be headless. |

Built-in backends report `focus_stolen=false`. They do not activate another app.

## Latency

Constants live in `bhashaflow_audio.budget`. CI measures the fixture path. The Muse file estimate is planning only.

| Slice | Budget |
| --- | --- |
| VAD decision | 30 ms |
| End of utterance (trailing silence) | 400 ms |
| Fixture transcription, segment already closed | 50 ms |
| Local confirmation | 150 ms |
| Barge-in cancel | 100 ms |
| Muse file transcription estimate | 800 ms, not asserted in CI |

The hangover is the largest local slice. It is how the offline path decides the speaker has finished. Muse endpointing replaces that wait on the realtime socket.

## Run the fixture path

No key, no microphone, no display:

```bash
uv run python -m bhashaflow_audio
```

That prints the four demo lines:

```text
open report.pdf in Downloads
read the invoice total
focus the recipient
attach the file
```

`transcribe_fixture()` is the same call. A live key switches `transcriber_from_env()` to Muse file transcription. Tests inject the HTTP transport and do not open a socket.
