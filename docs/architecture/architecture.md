# Architecture

Sections marked **(exists)** were verified in the repository on 2026-11-05 (branch `feature_ai_claude_2`, commit `853d1bf`). Sections marked **(planned)** come from recommendations or decisions and are not implemented. History that no longer describes the code is at the end (section 9) and in `docs/old/`.

## 1. Purpose and responsibility (exists)

STT turns **finished utterances** (PCM16 mono, each with its own sample rate) into text. Brain is the only caller: it uploads the utterances the microphone cut, and reads the text back. The service does no silence detection, does not decide what the text means, and calls no other service. Two engines sit behind one port (OpenAI Whisper API, or faster-whisper on the CPU), and an optional second, small local engine (the **wake-phrase gate**) lets Brain drop utterances that do not carry the wake phrase before they reach the paid engine. Port `8001`.

## 2. Structure (layers exist)

The same layered layout as `microphone_microservice` and the other OBLIVION services ([ADR-001](../decisions/ADR-001-layered-architecture.md)).

```
composition_root  ──▶  infrastructure  ──▶  application  ──▶  domain
 (chooses concretes)    inbound/outbound     ports+services    value objects, errors
```

Source-code dependencies point inward only. Runtime calls go outward (HTTP → service → engine) through ports owned by `application`.

```
SttHandler ──▶ SttTranscriptionPort ◀── SttService ──▶ TranscriptionPort ◀── OpenAIWhisperTranscription
(inbound)      (driving port)           (application)    (driven port)    ◀── LocalWhisperTranscription
                                             │                                   (outbound)
                                             ▼
                              domain: AudioUtterance, Utterance
```

`tests/architecture/test_dependency_rules.py` enforces this by parsing imports:

| Layer | May import | Must not import |
|---|---|---|
| `domain` | stdlib, `domain`, `shared_logging` | any other third-party package, `application`, `infrastructure`, `composition_root` |
| `application` | stdlib, `domain`, `application`, `shared_logging` | any other third-party package (so no `contracts`, fastapi, numpy, openai...), `infrastructure`, `composition_root` |
| `infrastructure/inbound` | anything third-party (fastapi, `contracts`...), `application`, `domain` | `infrastructure.outbound`, `composition_root` |
| `infrastructure/outbound` | anything third-party, `application`, `domain` | `infrastructure.inbound`, `composition_root` |
| `composition_root` | everything | none |
| `main_flow` | `composition_root`, `infrastructure.config`, third-party | `infrastructure.inbound`, `infrastructure.outbound` |

Two more rules of the same test: no `print()` outside `infrastructure`, and no module or folder named `utils`, `common` or `helpers`. Relative imports are not allowed.

| Layer | Path | Responsibility |
|---|---|---|
| Entry point | `main.py`, `main_flow/http.py` | Loads `.env`, reads the settings, starts logging, builds the container, runs uvicorn, stops the shared streams on shutdown |
| Domain | `domain/` | `AudioUtterance` (whole 16-bit samples at a positive rate), `Utterance` (text plus the audio it came from), `DomainError`, `InvalidAudioUtterance`. `domain/operations/` is an empty package |
| Application | `application/` | `SttService` (the use cases and the shared stream), the inbound port `SttTranscriptionPort`, the outbound port `TranscriptionPort`, DTOs, application errors |
| Infrastructure | `infrastructure/` | Settings (`ServerConfig`, `SttConfig`), the HTTP adapter, the two engines |
| Composition root | `composition_root/` | The only place concrete adapters are chosen and wired: the engine, the gate, the FastAPI app |

## 3. Current layout (exists)

```
main.py                                    calls main_flow.http.run_http()
main_flow/http.py                          .env -> settings -> logging -> container -> uvicorn -> shutdown cleanup
domain/
  errors.py                                DomainError, InvalidAudioUtterance
  value_objects/audio_utterance.py         AudioUtterance(audio, sample_rate)
  value_objects/utterance.py               Utterance(text, audio): what the gate's stream yields
application/
  errors.py                                ApplicationError, NoActiveStream, SharedStreamForwardingError, EngineNotConfigured, UnsupportedInput
  dtos/                                    ProcessStreamInboundDTO, SetStreamInboundDTO, ProcessBatchInboundDTO,
                                           TextStreamOutboundDTO, BatchTranscriptionOutboundDTO
  ports/inbound/stt_transcription_port.py  SttTranscriptionPort (driving)
  ports/outbound/transcription_port.py     TranscriptionPort (driven): transcribe_batch, is_available
  services/stt_service.py                  SttService: transcribes each utterance, owns the shared stream, no rules of its own
infrastructure/
  config/                                  ServerConfig, SttConfig (env -> frozen dataclasses)
  inbound/http/http_handler.py             SttHandler: the routes (main, and the gate with a prefix)
  inbound/http/http_envelope.py            success / failure -> ApiEnvelope
  inbound/http/http_error_mapper.py        exception -> HTTP status
  inbound/http/stream_events.py            SSE / NDJSON framing of STT_OUTBOUND events, heartbeat
  inbound/http/input_stream_response.py    the ack stream of an upload
  inbound/http/ndjson_audio_input.py       STT_INBOUND events -> AudioUtterance, validating the contract
  outbound/openai_whisper/                 OpenAIWhisperTranscription (WAV file -> whisper-1)
  outbound/local_whisper/                  LocalWhisperTranscription (faster-whisper, CPU)
composition_root/
  dependencies/stt_dependencies.py         new_transcription / new_gate_transcription / new_stt_service / new_http_app
  containers/http_container.py             HttpContainer(app, stt, gate), new_http_container
scripts/fetch_gate_model.py                downloads the gate model (deploy `prepare` step)
tests/                                     domain/ application/ infrastructure/ composition_root/ architecture/ (pytest, 90) + simple.py (end to end)
vendor/                                    the bundled contracts wheel (0.15.0)
```

## 4. Execution flow (exists)

1. **Start.** `run_http` loads `.env`, builds `ServerConfig` and `SttConfig`, starts `shared_logging`, and calls `new_http_container`: the engine is built (a missing key is `EngineNotConfigured`; a local model is loaded now), the gate too when enabled, then the FastAPI app with the `SttHandler` routes (the gate's under `/gate`) and the `TracingMiddleware`.
2. **Upload.** Brain's `POST /process/stream/set` hands the NDJSON body to `ndjson_utterances`, which decodes and validates `STT_INBOUND` events into `AudioUtterance`s as the bytes arrive. `SttService.set_stream` runs a forwarding task: each utterance goes to the engine as one batch (a worker thread for the local engine, a WAV file and an HTTP call for OpenAI), and a non-empty text is put on an in-memory queue (the shared stream). The request itself answers with an ack stream.
3. **Read.** `GET /process/stream/get` drains the queue through `text_event_stream`: `stream_started`, then `partial` and `completed` per text, a `heartbeat` after 15 s idle, an `error` event if the forwarding failed. SSE, or NDJSON on request.
4. **Single request.** `POST /process/stream` does the same without the queue: the utterances of the body are transcribed as the answer is written.
5. **Batch.** `POST /process/batch` transcribes one buffer and answers with the envelope.
6. **Gate.** With `STT_GATE_ENABLED=1` a second `SttService` (its own queue, its own local engine, `with_audio=True`) is served under `/gate`: its `completed` events carry the audio, so Brain can forward an utterance that held the wake phrase to the real engine through `/process/batch`.
7. **Stop.** On `SIGINT`/`SIGTERM` uvicorn returns, then `_cleanup` stops the shared stream of the main service and of the gate.

## 5. The wire contract (exists)

Text and audio events are the `contracts.stream` events `STT_INBOUND`, `STT_OUTBOUND` and the upload ack `UPLOAD_ACK`, encoded and decoded only with `contracts.stream.codec`; JSON answers are `contracts.api.common.envelope.ApiEnvelope` with `contracts.api.microservices` data (`HealthCheckResponse`, `AvailabilityResponse`, `STTProcessBatchResponse`). New events go into `contracts` first. Details of every route and event: [api.md](../api/api.md). The pipeline view is in `contracts/contracts/stream/README.md`.

## 6. Decision records at a glance

| ADR | Decision |
|---|---|
| [ADR-001](../decisions/ADR-001-layered-architecture.md) | The same layered layout as the other services, with the dependency rule tested |
| [ADR-002](../decisions/ADR-002-utterances-only-no-silence-detection.md) | STT only transcribes finished utterances; silence detection lives in the microphone (2026-10-05) |
| [ADR-003](../decisions/ADR-003-contract-streams-and-shared-stream.md) | The wire format is `contracts.stream` events; Brain uses an upload (`set`) and a read (`get`) on one shared stream (2026-09-20) |
| [ADR-004](../decisions/ADR-004-two-engines-behind-one-port.md) | OpenAI and local faster-whisper behind one `TranscriptionPort`, selected by `STT_ENGINE` |
| [ADR-005](../decisions/ADR-005-wake-phrase-gate.md) | The wake-phrase gate is a second service instance with a local engine, under `/gate` (2026-10-05) |
| [ADR-006](../decisions/ADR-006-no-direct-service-calls.md) | No autoloader: STT never pulls a stream from another service; Brain coordinates (2026-09-20) |
| [ADR-007](../decisions/ADR-007-http-status-mapping.md) | Natural HTTP statuses by exception type; a failure inside a started stream is an `error` event |

## 7. Persistence, errors, startup (exists)

- **Persistence:** none. The shared stream is an in-memory queue; nothing survives a restart. The only files are the OpenAI engine's temporary WAV per utterance and the models' cache ([monitoring.md](../operations/monitoring.md)).
- **Error handling:** sentinel errors per layer (`domain/errors.py`, `application/errors.py`); `map_error` turns them into statuses; the engines raise whatever their library raises, which becomes a `500`.
- **Start-up/shutdown:** fails fast on a missing key or an unloadable model; graceful stop of both shared streams.
- **Concurrency:** one event loop. The local engine runs in `asyncio.to_thread`; the OpenAI call too. A `set` transcribes its utterances one after another; the batch route, the gate and the main stream run independently of each other.

## 8. Known debt (exists as debt; each is also in the README)

1. **Model, compute type and threads of the local engine are constants** (`small.en`, `int8`, 2 threads). `STT_LANGUAGE=es` cannot work with the local engine. Planned: `STT_MODEL`, `STT_THREADS`, `STT_COMPUTE_TYPE` ([audit](../deployment_audit/stt.md)).
2. **Dev tools in the runtime requirements:** pytest, ruff, black and mypy are in `requirements.windows.txt` and `requirements.linux.txt`, so the deploy image installs them. Planned: a `requirements.dev.txt`.
3. **The model cache is not persistent in Docker**, and the deploy `prepare` step fetches nothing at build time. Needs `deployment/` (a volume for `HF_HOME`, run-time download). `scripts/fetch_gate_model.py` never fetches the main local model.
4. **Failures of a `set` reach Brain only through `get`.** The ack always ends with `input_completed`; the contract tests for an `error` in the ack use a fake service (`RecordingSetService`) that propagates the failure, which the real `SttService` does not.
5. **No limit and no timeout:** no cap on a request body or an utterance, no timeout or retry policy chosen for the OpenAI call.
6. **No authentication** ([security.md](../security/security.md)).
7. **Lint:** ruff, mypy and black are configured but not installed in this venv; ruff (from the microphone venv) reported 9 findings on 2026-10-01, not fixed on purpose.
8. **`tests/simple.py`** is an end-to-end script that needs a running service and real audio; it was not run in the last pass.
9. **`domain/operations/`** is an empty package left from the moment silence detection moved out.

## 9. History (not current)

* **2026-09-20, contract streams** (commit `19435bf`): text leaves as `contracts.stream` events, audio can arrive as `STT_INBOUND` NDJSON events, the upload answers with the `UPLOAD_ACK` stream, natural HTTP statuses, `StreamSettings` validation, the autoloader removed (archived in `docs/old/autoloader/`).
* **2026-10-05, the gate** (commit `e366de1`): a second local engine under `/gate` whose `completed` events carry the utterance audio; `STT_PROMPT` for the OpenAI engine (`e980937`).
* **2026-10-05, utterances only** (commit `79167ff`): silence detection moved to the microphone. `StreamSettings`, `PcmChunkAligner`, the silence rules and both engines' voice-activity loops were removed from here (they live in `microphone_microservice`: `UtteranceSegmenter`, `InputTreatment`, one `MICROPHONE_*` variable per treatment). The microphone sends one `utterance` event per utterance (contracts 0.12.0), Brain relays it as an STT inbound `utterance` event, and an engine is only `transcribe_batch` + `is_available`. The stream routes take no query settings; a raw-PCM upload is a `415`.
* **Earlier refactor (date not recorded; before the 2026-09-20 commit):** the inbound, service and outbound DTO triples became one DTO per use case; the two engines share one `TranscriptionPort`; the 660-line `fastapi_adapter.py` was split into handler, framing, upload response and decoder; `runtime/` was replaced by the shared `shared_logging` package; engine modules are imported lazily.
* **Contracts wheel (from the git log):** 0.8.0 (2026-09-25), 0.9.0 and 0.10.0 (2026-10-01), 0.11.0 (2026-10-05, the gate's `audio_base64`), 0.14.0 (2026-10-07), 0.15.0 (2026-10-08, current).
