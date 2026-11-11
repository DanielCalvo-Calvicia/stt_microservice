# ADR-002: STT only transcribes finished utterances; silence detection lives in the microphone

- **Status:** Accepted and built (commit `79167ff`).
- **Date:** 2026-10-05.

## Context

STT used to receive a raw PCM stream and cut it itself: both engines carried their own voice-activity loops (the OpenAI engine tracked a noise floor, the local engine removed a DC offset), with `StreamSettings` passed as query parameters and the silence arithmetic duplicated. The microphone is the one that knows the room, the device and the treatments (echo, noise), and it already has to decide when speech starts and ends.

## Decision

The microphone cuts the audio into utterances (`UtteranceSegmenter`, `InputTreatment`; every treatment is a `MICROPHONE_*` variable) and sends one `utterance` event per utterance (contracts 0.12.0). Brain relays each as an STT inbound `utterance` event. STT transcribes each utterance as one batch: an engine is only `transcribe_batch` and `is_available`. The stream routes take no query settings; a body that is not NDJSON events (for example raw PCM) is a `415`.

## Consequences

- The engines are small and testable; the duplicated silence code is gone from STT.
- The accuracy of an utterance (its start and end) is the microphone's responsibility, not STT's.
- A very long utterance is transcribed as one batch: STT has no cap on its length.
- Brain and the microphone must be on a compatible `contracts` version; the wheel in `vendor/` is the reference.
- `domain/operations/` stayed as an empty package ([architecture](../architecture/architecture.md), known debt 9).

> **Update 2026-11-11:** the empty `domain/operations/` package was removed.
