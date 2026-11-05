# ADR-005: The wake-phrase gate is a second service instance with a local engine, under `/gate`

- **Status:** Accepted and built (commit `e366de1`); not run with a real model in the last pass.
- **Date:** 2026-10-05.

## Context

With the OpenAI engine every utterance the microphone hears costs tokens, including room noise and conversations that are not addressed to the robot. Brain wants to answer only when the wake phrase (for example "Oblivion 306") is heard, and to pay for the real engine only then. The decision about what the text means belongs to Brain.

## Decision

With `STT_GATE_ENABLED=1` the service builds a second `SttService` with its own queue and a small local engine (`STT_GATE_MODEL`, default `tiny.en`, greedy decoding, `STT_GATE_PROMPT` as a hint). Its routes are the same as the main ones with the prefix `/gate` (`set`, `get`, `available`, `stop`; no batch and no single-request stream). Its `completed` events carry the utterance audio in `audio_base64` (contracts 0.11.0). Brain reads the text, decides, and sends the audio of an utterance that held the phrase to the real engine through `POST /process/batch`. `/available` is true only when both engines are ready. The gate is off by default.

## Consequences

- STT does not know the wake phrase or decide anything: the gate only returns text plus audio, so STT calls no other service ([ADR-006](ADR-006-no-direct-service-calls.md)).
- The gate's model is a second model in memory and needs a download on first use (`scripts/fetch_gate_model.py`, which in Docker fetches nothing at build time; see [deployment](../deployment/deployment.md)).
- Both streams are independent: stopping one does not stop the other (`/stop` and `/gate/stop`); shutdown stops both.
- The gate needs the same on Brain (`WAKE_PHRASE_ENABLED=1`) and the same words in `STT_GATE_PROMPT` and Brain's `WAKE_PHRASE`.
