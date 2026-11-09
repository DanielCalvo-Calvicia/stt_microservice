# ADR-004: OpenAI and local faster-whisper behind one port, chosen by `STT_ENGINE`

- **Status:** Accepted and built. The configurability of the local engine is **Planned**.
- **Date of this record:** 2026-11-05 (the decision predates it).

## Context

The robot can run with a paid cloud model (accurate, needs a key and the network, sends the audio out) or with a free local model (private, offline, needs a CPU that can run it, such as a Raspberry Pi). The choice is a deployment choice, not a code branch in the service.

## Decision

`TranscriptionPort` has two outbound adapters: `OpenAIWhisperTranscription` (`whisper-1`, temperature 0, one WAV file per utterance, optional `STT_PROMPT`) and `LocalWhisperTranscription` (faster-whisper on the CPU, `int8`). `STT_ENGINE=openai` (the default) selects the first; **any other value** selects the local engine. The composition root imports an engine module only when it is chosen, so running with one does not load the other's library. The OpenAI engine needs `OPENAI_API_KEY`: without it the start fails (`EngineNotConfigured`) instead of running with an empty key. `STT_LANGUAGE` is forced on both.

## Consequences

- A typo in `STT_ENGINE` selects the local engine and downloads a model; there is no validation of the value.
- The local model (`small.en`, English only), compute type and threads are constants today, so `STT_LANGUAGE=es` cannot work locally. The audit of 2026-11-04 recommends `STT_MODEL`, `STT_THREADS`, `STT_COMPUTE_TYPE` (defaults equal to the current values); **not built**.
- The audio of every utterance leaves the machine with the OpenAI engine ([security](../security/security.md)).
- Neither real engine was run in the last pass; the tests use fakes.

> **Update 2026-11-06 (T-01.2.2):** the configurability of the local engine is decided in [ADR-008](ADR-008-local-model-settings.md): `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE` are settings, with today's values as defaults, and the gate shares the threads and the compute type. They are read into `SttConfig` (T-01.2.2) and used by the engine and the gate since T-01.2.3 (2026-11-08). Neither real engine is "not run" any more: both ran on a Windows PC on 2026-11-06 (T-01.1.3, T-01.1.4).
