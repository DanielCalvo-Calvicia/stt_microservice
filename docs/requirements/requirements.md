# Requirements

Status as of 2026-11-08. **Done** means implemented and covered by the unit tests (`140 passed`, fake engines: no real model, no OpenAI call, no hardware); **Partly done** means some of it exists; **Planned** means recommended or decided and not built; **Not verified** means it exists but was not run for real recently. Every row names where it is built or decided (an ADR, a source file or a test).

Sources: the code of `stt_microservice` at commit `853d1bf` plus the uncommitted changes of the deployment plan (T-01, 2026-11-06 to 2026-11-08); the stream contract in `contracts` (`contracts/stream/README.md`, the 0.15.0 wheel); the maintainer's decisions recorded in the ADRs of `docs/decisions/`; the deployment audit of 2026-11-04 ([deployment_audit/stt.md](../deployment_audit/stt.md)).

## Functional: transcription

| ID | Requirement | Status | Where |
|---|---|---|---|
| FR-1 | The service transcribes **finished utterances** (PCM16 mono, each with its own sample rate), one batch per utterance. It does no silence detection and cuts no audio: the microphone does. | Done | ADR-002, `SttService._transcribed`, `test_stt_service.py` |
| FR-2 | An utterance whose transcription is empty (no speech) produces no text event. | Done | `SttService._transcribed`, `test_stt_service.py` |
| FR-3 | Two interchangeable engines behind one port: the OpenAI Whisper API (`whisper-1`, the default) and a local faster-whisper model on the CPU; `STT_ENGINE` selects (anything other than `openai` is local). Engine modules are imported only when selected. | Done; both engines were run for real on a Windows PC on 2026-11-06 (local: T-01.1.3, OpenAI: T-01.1.4); neither was run on a Raspberry Pi or in Docker | ADR-004, `stt_dependencies.py`, `test_transcription_engines.py` |
| FR-4 | `STT_LANGUAGE` is forced on every transcription (default `en`). | Done | `SttConfig`, both engines |
| FR-5 | `STT_PROMPT` biases the OpenAI engine toward words spelled as written (the wake phrase). | Done; real effect seen once on 2026-11-06: a 3 s silent buffer gave `you` without the prompt and an empty text with it (one sample each, not a conclusion) | `openai_whisper_transcription.py`, `test_transcription_engines.py` |
| FR-6 | The OpenAI engine fails at start-up when `OPENAI_API_KEY` is empty (`EngineNotConfigured`). | Done | `new_transcription`, `test_http_container.py` |
| FR-7 | The local engine resamples an utterance to Whisper's 16 kHz when it has another rate; the service never converts audio for another service. | Done | `_pcm_to_whisper_input`, `test_transcription_engines.py` |
| FR-8 | The model, the compute type and the thread count of the local engine are **settings** (`STT_MODEL`, `STT_THREADS`, `STT_COMPUTE_TYPE`; defaults `small.en`, `int8`, 2 threads; the gate shares the threads and the compute type). | Done: read into `SttConfig` (T-01.2.2) and used by the main model and the gate (T-01.2.3, 2026-11-08), with fake-model tests; a non-default value was **not** run with a real model | [ADR-008](../decisions/ADR-008-local-model-settings.md), `test_config.py`, `test_transcription_engines.py`, `test_http_container.py`, [environment-variables.md](../configuration/environment-variables.md) |

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
| FR-20 | With `STT_GATE_ENABLED=1` a second, local engine (`STT_GATE_MODEL`, default `base` since 2026-11-09, greedy decoding, `STT_GATE_PROMPT`, default `Oblivion 306.`, as hint) runs with its own shared stream under `/gate/process/stream/{set,get}`, `/gate/available` and `/gate/stop`. | Done; real model run on a Windows PC on 2026-11-06 (not on a Pi) | ADR-005, `new_gate_transcription`, `test_gate_http.py` |
| FR-21 | Each `completed` event of the gate's stream carries the utterance's audio in `audio_base64` (PCM16 mono, at the input rate) so Brain can send it to the real engine when the phrase was heard; the main stream leaves it empty. | Done | `SttService(with_audio=True)`, `test_gate_http.py` |
| FR-22 | `/available` is true only when the main engine **and** the gate are ready. | Done | `handle_available`, `test_gate_http.py` |

## Non-functional

| ID | Requirement | Status | Where |
|---|---|---|---|
| NFR-1 | Same layered layout as the other services; source dependencies point inward only (`composition_root -> infrastructure -> application -> domain`), checked by a test that parses the imports. `main_flow` imports neither adapter. | Done | ADR-001, `tests/architecture/test_dependency_rules.py` |
| NFR-2 | The service never calls another microservice; Brain is the only coordinator. | Done | ADR-006 |
| NFR-3 | Configuration only through environment variables with a documented `.env.example`; no port or URL is hardcoded; the default bind is `127.0.0.1`. | Done | `ServerConfig`, `SttConfig` |
| NFR-4 | The logs hold lengths, never the text or the audio of an utterance; the API key is never logged. | Done. By review of the code and two real runs (2026-11-06) the logs hold lengths and the model name, never the text or the audio, and no key. Since T-01.7 an OpenAI error reaches the batch answer, the stream `error` event and the log only as the fixed message `OpenAI request failed: <ErrorType> (HTTP <status>)`; before it, a wrong key came back as the library's text with its first 8 and last 4 characters (found in T-01.5 drill 5, T-01.1.5). Tests: `test_a_wrong_openai_key_*` and `test_openai_engine_*` (fake key). The local engine's errors are still the library's text (no secret found there). No test checks the log content of the other paths. | [monitoring.md](../operations/monitoring.md) |
| NFR-5 | Shutdown stops the shared stream of the main service and of the gate (a failure on one does not skip the other). | Done | `main_flow/http.py` `_cleanup` |
| NFR-6 | The unit tests need no model, no network and no hardware. | Done | `tests/` (fake engines, in-process ASGI) |
| NFR-7 | No authentication on the HTTP API; the only caller is Brain, on a trusted network. Service-to-service authentication is not designed in the workspace. | Decided / Not implemented | [security.md](../security/security.md) |
| NFR-8 | A request size limit, a timeout and a retry policy for the OpenAI call. | Planned | [security.md](../security/security.md) |
| NFR-9 | The local model survives a container restart (a persistent `HF_HOME` volume) and `prepare` fetches the main model too. | **Done on amd64 (2026-11-09):** `prepare` fetches the main model too (T-01.3.2). The volume for Docker (option B, [ADR-009](../decisions/ADR-009-model-delivery-in-docker.md)) was built in `deployment/` (T-02.2 to T-02.4) and proved with a real image (T-03.3): a restart (3.1 s), a recreate (5.4 s) and a rebuild did not download, the volume stayed at 551,212 KiB, and the model loaded from it with the network off. Not run on arm64 or on a Raspberry Pi (postponed) | [deployment.md](../deployment/deployment.md) |
| NFR-10 | The development tools (pytest, ruff, black, mypy) are not in the runtime requirements. | Done (T-01.4, 2026-11-08): they and `httpx` are in `requirements.dev.txt`; checked with two clean venvs (runtime only: none of them installed and the service answers `/health`; runtime plus dev: 140 passed) | `requirements.dev.txt`, [deployment.md](../deployment/deployment.md) |
| NFR-11 | The whole service is retested for real: OpenAI call, a faster-whisper model, `tests/simple.py`, a Raspberry Pi. | Partly done: on 2026-11-06 the OpenAI call, the local model, the gate and `tests/simple.py` ran on a Windows PC (T-01.1.2 to T-01.1.4), the failure drills ran (T-01.1.5) and the workspace pipeline check gave 84 passed, 18 skipped (T-01.1.6). Docker on amd64 was run on 2026-11-09 (T-03.1 to T-03.5, both engines). A Raspberry Pi is **postponed** (T-03.6, T-03.7); the wake-phrase round trip through Brain ran with a real microphone on 2026-11-09 (T-01.1.7): no phrase means no batch request, the phrase means exactly one, but the gate heard the name only 1 time in 4 (`tiny.en` 0 of 1, `base.en` 1 of 3); after the gate defaults changed (`base`, `Oblivion 306.`) a live re-test accepted only 2 of 8 phrases, caused by the microphone's late utterance start, not by the gate model; after the microphone got a pre-roll a third live run accepted 4 of 4 phrases that reached the gate (ADR-005) | README, *Status*; [tasks](../tasks/README.md) |

## Out of scope

Silence detection and cutting audio (microphone), deciding what the text means (Brain), calling other services, storing audio or text, speaker identification, translation, authentication of callers (not designed yet for the workspace), converting audio between services.
