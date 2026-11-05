# ADR-007: Natural HTTP statuses by exception type; a failure inside a started stream is an `error` event

- **Status:** Accepted and built (commit `19435bf`, extended on 2026-10-05).
- **Date:** 2026-09-20.

## Context

The first version caught every exception and answered `500`; an empty batch body, raised inside a `try/except Exception`, even came out as a `500`. A bare `RuntimeError` stood for "no stream".

## Decision

`infrastructure/inbound/http/http_error_mapper.py` maps by type: `NoActiveStream` -> `404`, `UnsupportedInput` (a body that is not NDJSON events) -> `415`, `InvalidAudioUtterance` -> `422`, anything else -> `500`; an empty batch body is `400`, answered explicitly. Errors are the application's and domain's own classes (`NoActiveStream` is still also a `RuntimeError`, `UnsupportedInput` and `InvalidAudioUtterance` also `ValueError`, so old callers keep working). JSON failures use the `ApiEnvelope` with the error text in `message` and `data`. Once a stream answer has started the status is already `200`: a failure then is an `error` event (`stream_failed`, `recoverable: true`) and the answer ends.

## Consequences

- A caller can tell "nothing was set" (`404`) from "your body is wrong" (`415`) from "the engine failed" (`500`).
- The `422` is reachable only for a failure raised before the first event; in practice a bad utterance inside a stream shows as an `error` event ([api](../api/api.md)).
- The failure text goes back to the caller as the exception message: it is not sanitised ([security](../security/security.md)).
