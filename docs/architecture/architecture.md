# Architecture

Sections marked **(exists)** were verified in the repository on 2026-11-11 (branch `feature_ai_claude_2`, HEAD `8ee7c7d`, not pushed, plus the uncommitted restructure of that day: ports, DTOs, dependencies and the inbound HTTP folder). Sections marked **(planned)** come from recommendations or decisions and are not implemented. History that no longer describes the code is at the end (section 9) and in `docs/old/`.

## 1. Purpose and responsibility (exists)

STT turns **finished utterances** (PCM16 mono, each with its own sample rate) into text. Brain is the only caller: it uploads the utterances the microphone cut, and reads the text back. The service does no silence detection, does not decide what the text means, and calls no other service. Two engines sit behind one port (OpenAI Whisper API, or faster-whisper on the CPU), and an optional second, small local engine (the **wake-phrase gate**) lets Brain drop utterances that do not carry the wake phrase before they reach the paid engine. Port `8001`.

## 2. Structure (layers exist)

The same layered layout as `microphone_microservice` and the other OBLIVION services ([ADR-001](../decisions/ADR-001-layered-architecture.md)).

```
composition_root  ──▶  infrastructure  ──▶  application  ──▶  domain
 (chooses concretes)    inbound/outbound     ports+services    value objects, errors
```

Source-code dependencies point inward only. Runtime calls go outward (HTTP → service → engine) through ports owned by `application`. There are three ports, one for each kind of component, and each lives in its own folder of `application/ports/`:

```
SttHandler ─implements▶ SttInboundPort          (inbound adapter port: the operations every inbound adapter offers)
SttHandler ─calls─────▶ SttServicePort ◀─implements─ SttService          (the service's own port: the use cases)
SttService ─calls─────▶ SttOutboundPort ◀─implements─ OpenAIWhisperTranscription, LocalWhisperTranscription
                         (outbound adapter port: what the service needs from an engine)
                              │
                              ▼
                domain: AudioUtterance, Utterance
```

A new inbound adapter (gRPC, a CLI...) implements `SttInboundPort` and a new engine implements `SttOutboundPort`, so each has the same functions as the ones already there. `SttInboundPort` has the same operations as the service with DTOs and no transport types (`health`, `is_available`, `stop`, `process_stream`, `set_stream`, `get_stream`, `process_batch`); `SttHandler` implements them by calling the service and its routes decode the HTTP request into those calls.

`tests/architecture/test_dependency_rules.py` enforces this by parsing imports:

| Layer | May import | Must not import |
|---|---|---|
| `domain` | stdlib, `domain`, `shared_logging` | any other third-party package, `application`, `infrastructure`, `composition_root` |
| `application` | stdlib, `domain`, `application`, `shared_logging` | any other third-party package (so no `contracts`, fastapi, numpy, openai...), `infrastructure`, `composition_root` |
| `infrastructure/inbound` | anything third-party (fastapi, `contracts`...), `application`, `domain` | `infrastructure.outbound`, `composition_root` |
| `infrastructure/outbound` | anything third-party, `application`, `domain` | `infrastructure.inbound`, `composition_root` |
| `composition_root` | everything | none |
| `main_flow` | `composition_root`, `infrastructure.config`, third-party | `infrastructure.inbound`, `infrastructure.outbound` |

Two more rules of the same test: no `print()` outside `infrastructure`, and no module or folder named `utils`, `common` or `helpers`, except `infrastructure/inbound/http/helpers/` (the folder name of the inbound adapter of `dynamics_microservice`, the reference for this layout). Relative imports are not allowed. `tests/architecture/test_dtos.py` keeps the DTOs apart: every one lives in `application/dtos/inbound` (what an inbound adapter hands to the application) or `application/dtos/outbound` (what the application hands back), and the folder, the file suffix and the class suffix agree. `tests/architecture/test_ports.py` checks the ports: the service, the HTTP handler and both engines implement theirs, each port declares exactly the operations listed here, and any class named `*Handler` under `infrastructure/inbound` or `*Transcription` under `infrastructure/outbound` must implement its port.

| Layer | Path | Responsibility |
|---|---|---|
| Entry point | `main.py`, `main_flow/http.py` | Loads `.env`, reads the settings, starts logging, builds the container, runs uvicorn, stops the shared streams on shutdown |
| Domain | `domain/` | `AudioUtterance` (whole 16-bit samples at a positive rate), `Utterance` (text plus the audio it came from), `DomainError`, `InvalidAudioUtterance`. Both types are value objects (frozen, no identity, no lifecycle), so there is no `domain/entities/`: the shared stream's state lives in `SttService` |
| Application | `application/` | `SttService` (the use cases and the shared stream), the service port `SttServicePort`, the inbound adapter port `SttInboundPort`, the outbound adapter port `SttOutboundPort`, DTOs, application errors |
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
  errors.py                                ApplicationError, NoActiveStream, SharedStreamForwardingError, EngineNotConfigured, UnsupportedInput, TranscriptionFailed
  dtos/inbound/                            requests: ProcessStreamInboundDTO, SetStreamInboundDTO, ProcessBatchInboundDTO
  dtos/outbound/                           responses: TextStreamOutboundDTO, BatchTranscriptionOutboundDTO
  ports/service/stt_service_port.py        SttServicePort: the service's own port (SttService implements it)
  ports/inbound/stt_inbound_port.py        SttInboundPort: what every inbound adapter offers (SttHandler implements it)
  ports/outbound/stt_outbound_port.py      SttOutboundPort: what every engine offers (both engines implement it): transcribe_batch, is_available
  services/stt_service.py                  SttService: transcribes each utterance, owns the shared stream, no rules of its own
infrastructure/
  config/                                  ServerConfig, SttConfig (env -> frozen dataclasses)
  inbound/http/http_handler.py             SttHandler(SttInboundPort): declares the endpoints (main, and the gate with a prefix) and wires each to its route; no request logic
  inbound/http/routes/                     one file per endpoint, a function taking the inbound port: health, available, stop, process_stream, set_stream, get_stream, process_batch
  inbound/http/response/http_envelope.py   success / failure -> ApiEnvelope
  inbound/http/response/stream_events.py   SSE / NDJSON framing of STT_OUTBOUND events, heartbeat
  inbound/http/response/input_stream_response.py   the ack stream of an upload
  inbound/http/response/output_format.py   SSE or NDJSON, from the Accept header
  inbound/http/response/stream_headers.py  the X-Action / X-Status headers of a stream
  inbound/http/errors/http_error_mapper.py exception -> HTTP status
  inbound/http/helpers/decode_body.py      the request body -> utterances (NDJSON only, else 415)
  inbound/http/helpers/ndjson_audio_input.py   STT_INBOUND events -> AudioUtterance, validating the contract
  inbound/http/helpers/media_types.py      the two media types (NDJSON, SSE)
  outbound/openai_whisper/                 OpenAIWhisperTranscription(SttOutboundPort) (WAV file -> whisper-1)
  outbound/local_whisper/                  LocalWhisperTranscription(SttOutboundPort) (faster-whisper, CPU)
composition_root/
  dependencies/transcription_dependency.py       new_transcription (the main engine: OpenAI or local)
  dependencies/gate_transcription_dependency.py  new_gate_transcription (the gate's small local engine)
  dependencies/stt_service_dependency.py         new_stt_service (one SttService per shared stream)
  dependencies/http_app_dependency.py            new_http_app (FastAPI app, routers, tracing middleware)
  containers/http_container.py             HttpContainer(app, stt, gate), new_http_container
scripts/fetch_gate_model.py                downloads the local models the settings need: main and/or gate (deploy `prepare` step)
tests/                                     domain/ application/ infrastructure/ composition_root/ architecture/ scripts/ (pytest, 152) + simple.py (end to end)
vendor/                                    the bundled contracts wheel (0.16.0, committed in `8ee7c7d`)
requirements.windows.txt, requirements.linux.txt   what the service runs on (the deploy tool installs them)
requirements.dev.txt                       pytest, httpx, ruff, black, mypy (the deploy tool never installs it)
```

## 4. Execution flow (exists)

1. **Start.** `run_http` loads `.env`, builds `ServerConfig` and `SttConfig`, starts `shared_logging`, and calls `new_http_container`, which uses the four dependency files: the engine is built (`new_transcription`: a missing key is `EngineNotConfigured`; a local model is loaded now), the gate's engine too when enabled (`new_gate_transcription`), one `SttService` for each (`new_stt_service`), then the FastAPI app (`new_http_app`) with the `SttHandler` routes (the gate's under `/gate`) and the `TracingMiddleware`.
2. **Upload.** Brain's `POST /process/stream/set` reaches `routes/set_stream.py` through `SttHandler`, which calls the inbound port's `set_stream`; `helpers/decode_body.py` gives the NDJSON body to `ndjson_utterances`, which decodes and validates `STT_INBOUND` events into `AudioUtterance`s as the bytes arrive. `SttService.set_stream` runs a forwarding task: each utterance goes to the engine as one batch (a worker thread for the local engine, a WAV file and an HTTP call for OpenAI), and a non-empty text is put on an in-memory queue (the shared stream). The request itself answers with an ack stream.
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
| [ADR-004](../decisions/ADR-004-two-engines-behind-one-port.md) | OpenAI and local faster-whisper behind one `SttOutboundPort`, selected by `STT_ENGINE` |
| [ADR-005](../decisions/ADR-005-wake-phrase-gate.md) | The wake-phrase gate is a second service instance with a local engine, under `/gate` (2026-10-05) |
| [ADR-006](../decisions/ADR-006-no-direct-service-calls.md) | No autoloader: STT never pulls a stream from another service; Brain coordinates (2026-09-20) |
| [ADR-007](../decisions/ADR-007-http-status-mapping.md) | Natural HTTP statuses by exception type; a failure inside a started stream is an `error` event |
| [ADR-008](../decisions/ADR-008-local-model-settings.md) | `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE` are settings; threads and compute type are shared by the main model and the gate (2026-11-06; built in T-01.2.2 and T-01.2.3) |
| [ADR-009](../decisions/ADR-009-model-delivery-in-docker.md) | In Docker the local models live in the named volume `oblivion-stt-models` and the `prepare` step runs against the real settings before the service starts (decided 2026-11-06, built in `deployment/` and proved on amd64 on 2026-11-09; arm64 not run) |

## 7. Persistence, errors, startup (exists)

- **Persistence:** none. The shared stream is an in-memory queue; nothing survives a restart. The only files are the OpenAI engine's temporary WAV per utterance and the models' cache ([monitoring.md](../operations/monitoring.md)).
- **Error handling:** sentinel errors per layer (`domain/errors.py`, `application/errors.py`); `map_error` turns them into statuses; the local engine raises whatever its library raises and the OpenAI engine raises `TranscriptionFailed` with a fixed message (T-01.7); either becomes a `500`.
- **Start-up/shutdown:** fails fast on a missing key, a bad `SERVICE_PORT` or `STT_THREADS`, or an unloadable model (see "What a failed start looks like" in [deployment.md](../deployment/deployment.md)); graceful stop of both shared streams.
- **Concurrency:** one event loop. The local engine runs in `asyncio.to_thread`; the OpenAI call too. A `set` transcribes its utterances one after another; the batch route, the gate and the main stream run independently of each other.

## 8. Known debt (exists as debt; each is also in the README)

1. ~~Model, compute type and threads of the local engine were constants.~~ **Resolved 2026-11-08** (T-01.2.2 and T-01.2.3, [ADR-008](../decisions/ADR-008-local-model-settings.md)): `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE` are settings used by the main model and the gate ([audit](../deployment_audit/stt.md)). The number is kept so other documents that cite "debt 1" stay valid.
2. ~~Dev tools in the runtime requirements.~~ **Resolved 2026-11-08** (T-01.4): pytest, httpx, ruff, black and mypy are in `requirements.dev.txt`, which the deploy tool never reads; `requirements.windows.txt` and `requirements.linux.txt` hold only what the service runs on. A venv built earlier keeps the tools until it is rebuilt. The number is kept so other documents that cite "debt 2" stay valid.
3. ~~The model cache is not persistent in Docker, and the deploy `prepare` step fetches nothing at build time.~~ **Resolved on amd64 on 2026-11-09** (T-03.3, real image and volume; arm64 postponed). Natively `scripts/fetch_gate_model.py` fetches the main local model too since T-01.3.2 (2026-11-08). The Docker part is **built in `deployment/` since 2026-11-09** (T-02.2 to T-02.4: volume `oblivion-stt-models` at `/models`, `HF_HOME=/models/huggingface` only for Docker, `prepare` run once in a throw-away container with the real `.env`) and proved with a real image on 2026-11-09: a restart, a recreate and a rebuild did not download again (T-03.1 to T-03.5).
4. **Failures of a `set` reach Brain only through `get`.** The ack always ends with `input_completed`; the contract tests for an `error` in the ack use a fake service (`RecordingSetService`) that propagates the failure, which the real `SttService` does not.
5. **No limit and no timeout:** no cap on a request body or an utterance, no timeout or retry policy chosen for the OpenAI call.
6. **No authentication** ([security.md](../security/security.md)).
7. **Lint:** ruff, mypy and black are configured but not installed in this venv; ruff (from the microphone venv) reported 9 findings on 2026-10-01, not fixed on purpose.
8. **`tests/simple.py`** is an end-to-end script that needs a running service. It ran once, on 2026-11-06 against a scratch deployment (T-01.1.3): it only checks `/health` and `/available`, transcribes nothing, and on a Windows console needs `python -X utf8`.
9. ~~`domain/operations/` was an empty package left from the moment silence detection moved out.~~ **Resolved 2026-11-11:** the package was removed (a dead-code scan of the whole service found nothing else unused). The number is kept so other documents that cite "debt 9" stay valid.
10. **No lock file.** Since T-01.6 (2026-11-08) the seven packages the service imports are pinned exactly, but the packages they depend on (ctranslate2, onnxruntime, starlette, huggingface_hub, ...) are not, so a new release of one of those can still change a deploy. The `numpy` line falls back to an open bound on Python 3.11. Dependency scanning does not exist ([security](../security/security.md)).

## 9. History (not current)

* **2026-09-20, contract streams** (commit `19435bf`): text leaves as `contracts.stream` events, audio can arrive as `STT_INBOUND` NDJSON events, the upload answers with the `UPLOAD_ACK` stream, natural HTTP statuses, `StreamSettings` validation, the autoloader removed (archived in `docs/old/autoloader/`).
* **2026-10-05, the gate** (commit `e366de1`): a second local engine under `/gate` whose `completed` events carry the utterance audio; `STT_PROMPT` for the OpenAI engine (`e980937`).
* **2026-10-05, utterances only** (commit `79167ff`): silence detection moved to the microphone. `StreamSettings`, `PcmChunkAligner`, the silence rules and both engines' voice-activity loops were removed from here (they live in `microphone_microservice`: `UtteranceSegmenter`, `InputTreatment`, one `MICROPHONE_*` variable per treatment). The microphone sends one `utterance` event per utterance (contracts 0.12.0), Brain relays it as an STT inbound `utterance` event, and an engine is only `transcribe_batch` + `is_available`. The stream routes take no query settings; a raw-PCM upload is a `415`.
* **Earlier refactor (date not recorded; before the 2026-09-20 commit):** the inbound, service and outbound DTO triples became one DTO per use case; the two engines share one `TranscriptionPort` (renamed `SttOutboundPort` on 2026-11-11); the 660-line `fastapi_adapter.py` was split into handler, framing, upload response and decoder; `runtime/` was replaced by the shared `shared_logging` package; engine modules are imported lazily.
* **Contracts wheel (from the git log):** 0.8.0 (2026-09-25), 0.9.0 and 0.10.0 (2026-10-01), 0.11.0 (2026-10-05, the gate's `audio_base64`), 0.14.0 (2026-10-07), 0.15.0 (2026-10-08), 0.16.0 (bundled in `8ee7c7d`, 2026-11-09, the committed one; the venv `windows` still has 0.15.0 installed).
* **2026-11-06 to 2026-11-09, deployment readiness** (the plan in `docs/tasks`, commit `8ee7c7d`, not pushed): both engines and the gate run for real on a Windows PC (T-01.1); the OpenAI engine's failures are a fixed message ([ADR-007](../decisions/ADR-007-http-status-mapping.md) update); `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE` ([ADR-008](../decisions/ADR-008-local-model-settings.md)); `scripts/fetch_gate_model.py` fetches the main model too; the dev tools moved to `requirements.dev.txt`; the Docker model delivery ([ADR-009](../decisions/ADR-009-model-delivery-in-docker.md)) was built in `deployment/` and proved on amd64 on 2026-11-09 (T-02, T-03); the gate defaults became `base` and `Oblivion 306.` ([ADR-005](../decisions/ADR-005-wake-phrase-gate.md)).
* **2026-11-11, the layers made explicit** (uncommitted): three ports, one per kind of component (`SttServicePort`, `SttInboundPort`, `SttOutboundPort`, the last one renamed from `TranscriptionPort`); the DTOs split into `application/dtos/inbound` and `outbound`; one dependency file per object in `composition_root/dependencies/`; the inbound HTTP folder laid out like `dynamics_microservice` (`http_handler.py` wires, `routes/`, `response/`, `errors/`, `helpers/`); the empty `domain/operations/` and the stale `.engram/` notes removed. Behaviour and routes did not change; new tests `test_ports.py` and `test_dtos.py` (152 in all). See the updates in [ADR-001](../decisions/ADR-001-layered-architecture.md), [ADR-004](../decisions/ADR-004-two-engines-behind-one-port.md) and [ADR-007](../decisions/ADR-007-http-status-mapping.md).
