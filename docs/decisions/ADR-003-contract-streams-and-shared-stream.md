# ADR-003: The wire format is `contracts.stream` events, on one shared stream

- **Status:** Accepted and built (commit `19435bf`; the shape of the input changed in [ADR-002](ADR-002-utterances-only-no-silence-detection.md)).
- **Date:** 2026-09-20.

## Context

Brain and STT run for as long as the robot is on: Brain has audio to send at some moments and wants text back at others, and the two must not block each other. The workspace has one definition of what services exchange: the `contracts` package.

## Decision

- Everything on the wire is a `contracts.stream` event (`STT_INBOUND`, `STT_OUTBOUND`, and the upload ack `UPLOAD_ACK`), encoded and decoded with `contracts.stream.codec`; JSON answers use `ApiEnvelope`. No event JSON is hand-written.
- Brain uses **two connections**: `POST /process/stream/set` (a long upload of NDJSON events) and `GET /process/stream/get` (a long read of the text events), joined by one in-memory queue in `SttService`. A new `set` replaces the previous one; `POST /stop` ends it.
- The upload answers at once with an ack stream that ends in `input_completed` (the answer to the **request**, never mistaken for a transcript). The read has a `heartbeat` every 15 s when idle.
- Framing is SSE by default and NDJSON when the request says `Accept: application/x-ndjson`; the events are the same.
- `POST /process/stream` (single request) and `POST /process/batch` (one buffer) remain for simple callers and for tests.

## Consequences

- Brain keeps the read open while it uploads; a failure while transcribing reaches Brain as an `error` event on the read.
- The ack of a `set` does **not** report a failure of the audio it carried (the forwarding task catches it and the ack ends with `input_completed`). Brain must watch `get` ([architecture](../architecture/architecture.md), known debt 4).
- The queue is delivered once: one reader is expected, and nothing is replayed.
- A new event needs a change in `contracts` first, then a new wheel here.
