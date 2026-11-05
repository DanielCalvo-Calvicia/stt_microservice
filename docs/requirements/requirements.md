# Requirements

Status as of 2026-11-05. **Done** means implemented and covered by the unit tests (`90 passed`, fake engines: no real model, no OpenAI call, no hardware); **Partly done** means some of it exists; **Planned** means recommended or decided and not built; **Not verified** means it exists but was not run for real recently. Every row names where it is built or decided (an ADR, a source file or a test).

Sources: the code of `stt_microservice` at commit `853d1bf`; the stream contract in `contracts` (`contracts/stream/README.md`, the 0.15.0 wheel); the maintainer's decisions recorded in the ADRs of `docs/decisions/`; the deployment audit of 2026-11-04 ([deployment_audit/stt.md](../deployment_audit/stt.md)).

## Functional: transcription

| ID | Requirement | Status | Where |
|---|---|---|---|
| FR-1 | The service transcribes **finished utterances** (PCM16 mono, each with its own sample rate), one batch per utterance. It does no silence detection and cuts no audio: the microphone does. | Done | ADR-002, `SttService._transcribed`, `test_stt_service.py` |
| FR-2 | An utterance whose transcription is empty (no speech) produces no text event. | Done | `SttService._transcribed`, `test_stt_service.py` |
| FR-3 | Two interchangeable engines behind one port: the OpenAI Whisper API (`whisper-1`, the default) and a local faster-whisper model on the CPU; `STT_ENGINE` selects (anything other than `openai` is local). Engine modules are imported only when selected. | Done; real engines **Not verified** | ADR-004, `stt_dependencies.py`, `test_transcription_engines.py` |
| FR-4 | `STT_LANGUAGE` is forced on every transcription (default `en`). | Done | `SttConfig`, both engines |
| FR-5 | `STT_PROMPT` biases the OpenAI engine toward words spelled as written (the wake phrase). | Done; real effect **Not verified** | `openai_whisper_transcription.py`, `test_transcription_engines.py` |
| FR-6 | The OpenAI engine fails at start-up when `OPENAI_API_KEY` is empty (`EngineNotConfigured`). | Done | `new_transcription`, `test_http_container.py` |
| FR-7 | The local engine resamples an utterance to Whisper's 16 kHz when it has another rate; the service never converts audio for another service. | Done | `_pcm_to_whisper_input`, `test_transcription_engines.py` |
| FR-8 | The model, the compute type and the thread count of the local engine are **settings** (the audit recommends `STT_MODEL`, `STT_THREADS`, `STT_COMPUTE_TYPE`; today they are constants: `small.en`, `int8`, 2 threads). | Planned | audit, [environment-variables.md](../configuration/environment-variables.md) |

## Functional: routes

| ID | Requirement | Status | Where |
|---|---|---|---|
| FR-10 | `GET /health` (liveness) and `GET /available` (engine ready, the gate's too when on). | Done | `SttHandler`, `test_http_routes.py` |
| FR-11 | A **shared stream**: Brain uploads with `POST /process/stream/set` (NDJSON `STT_INBOUND`) and reads with `GET /process/stream/get` (`STT_OUTBOUND`); a new `set` replaces the previous; `POST /stop` ends it; `get` before any `set` is a `404`. | Done | ADR-003, `SttService`, `test_stt_service.py`, `test_http_handler.py` |
| FR-12 | The upload answers at once with an ack stream (`stream_started`, then `input_completed`); the transcripts and **their failures** (a bad event, an engine error) are in `get`. Probed against the real service on 2026-11-05: a non-mono upload gives `input_completed` in the ack and an `error` event in `get`. The ack tests in `test_stream_contract.py` use a fake service that propagates the failure into the ack, so they do not cover this. | Done (behaviour); the ack-`error` tests describe a path the real service does not take | `InputStreamResponse`, `SttService._forward_stream_to_queue`, `test_http_handler.py`, `test_stream_contract.py` |
| FR-13 | `POST /process/stream`: NDJSON `utterance` events in the body, SSE text events in the answer (`partial` + `completed` per utterance; an empty `completed` when no utterance gave text). | Done | `test_http_handler.py` |
| FR-14 | `POST /process/batch?sample_rate=`: one PCM buffer in, `{text}` in the envelope out; an empty body is `400`. | Done | `test_http_routes.py` |
| FR-15 | Text events are framed as SSE by default and as NDJSON when the request says `Accept: application/x-ndjson`; a `heartbeat` every 15 s on an idle `get`. | Done | `stream_events.py`, `test_http_handler.py` |
| FR-16 | A body that is not NDJSON is a `415` before it is read; an empty batch body `400`; no stream `404`; an invalid utterance `422` (before the stream starts); anything else `500`. After a stream has started a failure is an `error` event (`stream_failed`). | Done | ADR-007, `http_error_mapper.py`, tests |
| FR-17 | The input is validated against the `STT_INBOUND` contract as it arrives: sequence numbers, a `stream_started` first, `channels == 1`, valid base64, whole 16-bit samples. | Done | `ndjson_audio_input.py`, `test_stream_contract.py` |
| FR-18 | Every JSON answer that is not a stream uses the `ApiEnvelope`; every event uses `contracts.stream` and its codec, never hand-written JSON. | Done | ADR-003, `http_envelope.py` |

## Functional: the wake-phrase gate

| ID | Requirement | Status | Where |
|---|---|---|---|
| FR-20 | With `STT_GATE_ENABLED=1` a second, local engine (`STT_GATE_MODEL`, default `tiny.en`, greedy decoding, `STT_GATE_PROMPT` as hint) runs with its own shared stream under `/gate/process/stream/{set,get}`, `/gate/available` and `/gate/stop`. | Done; real model **Not verified** | ADR-005, `new_gate_transcription`, `test_gate_http.py` |
| FR-21 | Each `completed` event of the gate's stream carries the utterance's audio in `audio_base64` (PCM16 mono, at the input rate) so Brain can send it to the real engine when the phrase was heard; the main stream leaves it empty. | Done | `SttService(with_audio=True)`, `test_gate_http.py` |
| FR-22 | `/available` is true only when the main engine **and** the gate are ready. | Done | `handle_available`, `test_gate_http.py` |

## Non-functional

| ID | Requirement | Status | Where |
|---|---|---|---|
| NFR-1 | Same layered layout as the other services; source dependencies point inward only (`composition_root -> infrastructure -> application -> domain`), checked by a test that parses the imports. `main_flow` imports neither adapter. | Done | ADR-001, `tests/architecture/test_dependency_rules.py` |
| NFR-2 | The service never calls another microservice; Brain is the only coordinator. | Done | ADR-006 |
| NFR-3 | Configuration only through environment variables with a documented `.env.example`; no port or URL is hardcoded; the default bind is `127.0.0.1`. | Done | `ServerConfig`, `SttConfig` |
| NFR-4 | The logs hold lengths, never the text or the audio of an utterance; the API key is never logged. | Done by review of the code (no test checks the log content); an exception text from a library is **not verified** | [monitoring.md](../operations/monitoring.md) |
| NFR-5 | Shutdown stops the shared stream of the main service and of the gate (a failure on one does not skip the other). | Done | `main_flow/http.py` `_cleanup` |
| NFR-6 | The unit tests need no model, no network and no hardware. | Done | `tests/` (fake engines, in-process ASGI) |
| NFR-7 | No authentication on the HTTP API; the only caller is Brain, on a trusted network. Service-to-service authentication is not designed in the workspace. | Decided / Not implemented | [security.md](../security/security.md) |
| NFR-8 | A request size limit, a timeout and a retry policy for the OpenAI call. | Planned | [security.md](../security/security.md) |
| NFR-9 | The local model survives a container restart (a persistent `HF_HOME` volume) and `prepare` fetches the main model too. | Planned (needs `deployment/`) | [deployment.md](../deployment/deployment.md) |
| NFR-10 | The development tools (pytest, ruff, black, mypy) are not in the runtime requirements. | Planned | audit, [architecture.md](../architecture/architecture.md) |
| NFR-11 | The whole service is retested for real: OpenAI call, a faster-whisper model, `tests/simple.py`, a Raspberry Pi. | Planned | README, *Status* |

## Out of scope

Silence detection and cutting audio (microphone), deciding what the text means (Brain), calling other services, storing audio or text, speaker identification, translation, authentication of callers (not designed yet for the workspace), converting audio between services.
