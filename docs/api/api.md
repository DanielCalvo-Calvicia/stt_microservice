# HTTP API of the service

What `python main.py` answers today, checked against the code (`infrastructure/inbound/http/`, `composition_root/dependencies/stt_dependencies.py`) and the tests. The only caller is Brain; there is no authentication and no CORS (see [security](../security/security.md)). The wire format is the `contracts` package (the 0.15.0 wheel in `vendor/`): events are encoded and decoded only with `contracts.stream.codec`.

Audio is **PCM16, little-endian, mono**. The service never converts it; the local engine resamples to Whisper's 16 kHz inside its own call when an utterance has another rate.

## Routes

| Method and path | Purpose | State |
|---|---|---|
| `GET /health` | Liveness: `200` whenever the process answers; touches no engine | Built |
| `GET /available` | Whether the engine is ready (and the gate too, when it is on) | Built |
| `POST /process/stream/set` | Brain uploads NDJSON events; the transcripts go to the shared stream; the request answers with an ack stream | Built |
| `GET /process/stream/get` | Reads the transcripts of the shared stream | Built |
| `POST /process/stream` | Single-request variant: NDJSON `utterance` events in the body, text events in the answer | Built |
| `POST /process/batch?sample_rate=16000` | Transcribe one PCM buffer | Built |
| `POST /stop` | Stop the shared stream | Built |
| `POST /gate/process/stream/set`, `GET /gate/process/stream/get`, `GET /gate/available`, `POST /gate/stop` | The same four on the wake-phrase gate's own shared stream and local engine; only with `STT_GATE_ENABLED=1` | Built |
| `GET /docs`, `/redoc`, `/openapi.json` | FastAPI's own documentation of the routes | Built (on by default) |

The gate has no `/gate/process/stream` and no `/gate/process/batch`; `/health` is not repeated under `/gate`. Without `STT_GATE_ENABLED=1` every `/gate/...` path is a `404`. Another method on a known path is `405` (FastAPI default).

## The shared stream

There is one shared stream per handler (the main one, and the gate's own). Brain opens `set` (a long upload) and `get` (a long read) at the same time.

```
POST /process/stream/set   body: NDJSON events of STT_INBOUND ──► ack stream: stream_started ... input_completed | error
GET  /process/stream/get   ──► text events of STT_OUTBOUND: stream_started, then partial + completed per utterance, heartbeat when idle
```

- A new `set` cancels the previous one and replaces the stream. `POST /stop` cancels a running `set` and ends the stream for its reader; with no `set` running it only ends the stream.
- The stream is one queue: each text item is delivered once, to the reader that takes it (one reader is expected). `get` before any `set` is a `404`.
- If the transcription fails while a `set` runs, the reader of `get` receives an `error` event.

### Input: `STT_INBOUND` NDJSON events

`Content-Type: application/x-ndjson`; one event per line. Anything else is a `415` (checked before the body is read).

| Event | Payload | What the service does |
|---|---|---|
| `stream_started` | `sample_rate`, `channels` | `channels` must be `1` (else the stream fails); remembers `sample_rate` as the rate of a later `completed` |
| `utterance` | `bytes_base64`, `sample_rate` | One finished utterance: transcribed as one batch at its own `sample_rate` |
| `completed` | `output_bytes_base64` | If it carries audio, it is one more utterance at the announced rate; with no audio it is ignored |
| `heartbeat` | none | Ignored |
| `error` | `code`, `message` | The stream fails with `code: message` |

The decoder validates the contract as it goes: a malformed event, a wrong sequence number, a missing `stream_started` or audio that is not valid base64 fails the stream. **Where the failure shows depends on the route:** on `POST /process/stream` it is an `error` event in that answer; on `set` the failure is delivered to the reader of `get` as an `error` event, and the ack stream of the `set` request still ends with `input_completed` (the service catches it in the forwarding task; see the ack section). An utterance must be a whole number of 16-bit samples at a positive rate (`InvalidAudioUtterance` otherwise). An utterance whose transcription is empty (no speech in it) produces nothing.

### Output: `STT_OUTBOUND` events

Framing: **SSE** by default (`text/event-stream`), **NDJSON** when the request has `Accept: application/x-ndjson`. The same events in both.

| Event | Payload | When |
|---|---|---|
| `stream_started` | none | first event of every answer |
| `partial` | `text` | one per transcribed utterance, just before its `completed`; it has the same text (the engines only produce finished utterances, there is no interim hypothesis) |
| `completed` | `reason` (`completed`), `output` (the text), `audio_base64` | one per transcribed utterance; `audio_base64` is empty except on the gate's stream, where it is the utterance's audio (PCM16 mono, at the input rate) |
| `heartbeat` | none | `GET .../get` only: after 15 s with nothing to send |
| `error` | `code` (`stream_failed`), `message`, `recoverable` (`true`) | the transcription or the stream failed after the answer started; the answer ends |

`POST /process/stream` answers SSE with `stream_started` and the events above; when no utterance gave any text it ends with one `completed` whose `output` is empty. `GET /process/stream/get` never sends that empty `completed`.

### The ack stream of `set`

`POST /process/stream/set` answers `200` at once with headers `X-Action: set_stream`, `X-Status: accepted` and `X-Message`, keeps the response open while it reads the body, and ends with:

| Last event | Meaning |
|---|---|
| `input_completed` (`reason: end_of_input`) | the forwarding of the body to the shared stream ended: the sender closed its stream, **or** reading, decoding or transcribing it failed (that failure went to the reader of `get`) |
| `error` (`stream_failed`) | only if the use case itself raises something the forwarding task did not catch; not reachable with the current service (nothing in the tests produces it) |

SSE by default; NDJSON with `Accept: application/x-ndjson`. `input_completed` is the answer to the **request**: it does not say the audio was transcribed without error, the transcripts and their failures are in `get`. Brain must therefore read `get` for errors.

## Batch: `POST /process/batch?sample_rate=16000`

The body is one raw PCM buffer (no JSON). `sample_rate` defaults to `16000`. The answer is the envelope with `data` = `STTProcessBatchResponse{text}`. An empty body is `400` "No audio data provided". The text is returned as the engine produced it (the stream routes also strip it). Checked on 2026-11-06: the local engine's batch text starts with a space (Whisper's own), the OpenAI engine's does not, so a caller that compares texts must strip.

## Envelope

Every non-stream JSON answer is `contracts.api.common.envelope.ApiEnvelope`:

```json
{"action": "process_batch", "status": "success", "status_code": 200, "message": "Audio processed successfully", "timestamp": "...", "data": {"text": "..."}}
```

`GET /health` has `data` = `HealthCheckResponse{healthy: true}`; `GET /available` has `data` = `AvailabilityResponse{is_available}`. On a failure `message` is `"<what failed>: <error text>"` and `data` is the error text.

## Errors

The mapping is in `infrastructure/inbound/http/http_error_mapper.py`.

| Status | When |
|---|---|
| 400 | `POST /process/batch` with an empty body |
| 404 | `GET /process/stream/get` before any `set`; any `/gate/...` path with the gate off |
| 415 | `set` or `POST /process/stream` with a `Content-Type` that is not NDJSON |
| 422 | An invalid utterance (non-positive sample rate, half a sample) raised **before** the stream starts |
| 500 | Anything else: an engine failure in `/process/batch`, `/available` or `/stop`, an unexpected error. A failure of the OpenAI call has the fixed message `OpenAI request failed: <ErrorType> (HTTP <status>)` (for example `AuthenticationError (HTTP 401)` for a wrong key), never the library's text |

Once a stream answer has started (status `200` already sent) a failure cannot change the status: it is an `error` event (`stream_failed`) and the answer ends. This is why a bad utterance inside `set` or `POST /process/stream` shows as an `error` event (in `get` or in that answer) and not as a `422` in practice; the `422` exists for a failure raised before the first event (covered by a test that makes the port raise it).

## Headers of the stream answers

`Cache-Control: no-cache`, `Connection: keep-alive`, `X-Action`, `X-Status`, `X-Message`, `X-Timestamp`. The server keeps connections alive for 60 s (`timeout_keep_alive`).
