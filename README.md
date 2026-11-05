# stt_microservice

HTTP service (Python, FastAPI, port **8001**) that turns finished utterances (16-bit mono PCM) into text, with the OpenAI Whisper API or a local `faster-whisper` model. It does no silence detection: the microphone service cuts the audio into utterances and Brain hands each one over as an `utterance` event of the STT inbound contract. It answers with `contracts.stream` events. Only Brain calls it. An optional **wake-phrase gate** (a second, small local model) lets Brain drop utterances that do not carry the wake phrase before they reach the paid engine.

Part of OBLIVION (see `../README.md`). Repository: `stt_microservice`, branch `feature_ai_claude_2`.

```
microphone ──utterances──► Brain ──STT_INBOUND (NDJSON)──► POST /process/stream/set ──► engine ──┐
                             ▲                                                                   │
                             └──────────STT_OUTBOUND (SSE / NDJSON)◄── GET /process/stream/get ◄─┘
engine = OpenAI Whisper API (default)  or  local faster-whisper  (+ optional gate under /gate)
```

## Status

Working, needs a retest after the recent changes. The code and the unit tests agree; the real engines and the end-to-end script have not been run recently.

| Area | State |
|---|---|
| Shared stream: `POST /process/stream/set`, `GET /process/stream/get`, `POST /stop` | Built, covered by tests with fake engines |
| Single-request stream `POST /process/stream` and `POST /process/batch` | Built, covered by tests |
| OpenAI engine (`whisper-1`, optional `STT_PROMPT`) | Built; the real API was **not** called in the last pass |
| Local engine (faster-whisper on the CPU) | Built; the real model was **not** loaded in the last pass. Model, threads and compute type are constants (**Planned**: settings, see the audit) |
| Wake-phrase gate under `/gate/...` (`STT_GATE_ENABLED=1`) | Built, covered by tests with fake engines; not run with a real model in the last pass |
| `contracts` events, envelope, error mapping | Built (contracts 0.15.0 wheel in `vendor/`) |
| Silence detection | **Not here by design**: it lives in `microphone_microservice` |
| Authentication, CORS, request size limit | **Not built** (see [docs/security/security.md](docs/security/security.md)) |
| Docker image | None in this repo: `deployment/` builds it; the model cache is not persistent there (see [docs/deployment/deployment.md](docs/deployment/deployment.md)) |

## Requirements

- Python 3.14 in the service venv `windows\Scripts\python.exe` (the deployment Docker image uses 3.12; `pyproject.toml` targets 3.11).
- `OPENAI_API_KEY` when `STT_ENGINE=openai` (the default). Network access to the OpenAI API in that case.
- For a local engine or the gate: `faster-whisper` (in the requirements), enough RAM for the model and network on the first start to download it.
- The shared logging package (`../shared-logging`) and the bundled `contracts` wheel (`vendor/`).

## Quick start

```bash
pip install -r requirements.windows.txt   # Linux / Raspberry Pi: requirements.linux.txt
cp .env.example .env                       # then set OPENAI_API_KEY, or STT_ENGINE=local
python main.py
```

PowerShell, with the service's own venv:

```powershell
Copy-Item .env.example .env
& windows\Scripts\python.exe main.py
curl http://127.0.0.1:8001/available
```

Rules for the file: configuration is read from the environment and a `.env` next to `main.py` is loaded too (a variable already set in the process wins). `.env` is ignored by git; never commit it and never put a real key in `.env.example`. The default bind address is `127.0.0.1`; set `SERVICE_HOST` (for example `0.0.0.0`) when Brain runs on another machine. The service stops at start-up with `EngineNotConfigured` when `STT_ENGINE=openai` and the key is empty.

## Configuration

The full table (defaults, who reads each variable, which are secret) is in [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md); the template with comments is [.env.example](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_NAME` / `SERVICE_HOST` / `SERVICE_PORT` | `STT Microservice` / `127.0.0.1` / `8001` | API title and log name, bind address and port |
| `LOG_LEVEL` | `INFO` | Read by `shared_logging` (`TRACE`, `DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`, `CRITICAL`) |
| `STT_ENGINE` | `openai` | `openai` = Whisper API (`whisper-1`); any other value (for example `local`) = local faster-whisper (`small.en`, CPU, int8). Case-insensitive |
| `STT_LANGUAGE` | `en` | ISO-639-1 code forced on the transcription (empty falls back to `en`) |
| `STT_PROMPT` | empty | OpenAI engine only: words the model should spell as written (for example `Oblivion 306`) |
| `STT_GATE_ENABLED` | `0` | `1` = also run the wake-phrase gate under `/gate/...` |
| `STT_GATE_MODEL` | `tiny.en` | faster-whisper model of the gate (greedy decoding) |
| `STT_GATE_PROMPT` | `Oblivion 306` | Hint so the gate spells the wake phrase right (empty = none) |
| `OPENAI_API_KEY` | empty | **Secret.** Required when `STT_ENGINE=openai`. Never log or echo it |

`LOG_FORMAT`, `LOG_OUTPUT`, `ENVIRONMENT` and `TRACE_EXPORT_*` are read by the shared logging package, not by this service: see [`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md). Local models download on first use into the Hugging Face cache (`HF_HOME`, default `~/.cache/huggingface`; not read by this service).

## Endpoints

Detail, event shapes and errors: [docs/api/api.md](docs/api/api.md).

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness (`200` whenever the process answers) |
| GET | `/available` | `data` is `AvailabilityResponse{is_available}`: whether the engine (and the gate, when on) is ready |
| POST | `/process/stream/set` | Brain's upload: NDJSON events of `STT_INBOUND`. Answers with an ack stream (`stream_started`, then `input_completed` or `error`) |
| GET | `/process/stream/get` | Reads the shared stream's text events (`STT_OUTBOUND`), heartbeat every 15 s; `404` if nothing was set |
| POST | `/process/stream` | Single-request variant: NDJSON `utterance` events in, SSE events out |
| POST | `/process/batch?sample_rate=16000` | One PCM buffer in, `data` is `STTProcessBatchResponse{text}`; `400` if the body is empty |
| POST | `/stop` | Stops the shared stream |
| POST/GET | `/gate/process/stream/{set,get}`, `/gate/available`, `/gate/stop` | Only with `STT_GATE_ENABLED=1`: the same on the gate's own stream and local engine; each `completed` event also carries the audio in `audio_base64` |

`/docs`, `/redoc` and `/openapi.json` (FastAPI) are on. JSON answers use the envelope `action / status / status_code / message / timestamp / data` (`contracts.api.common.envelope.ApiEnvelope`). Audio is PCM16 mono and the service never converts it (the local engine only resamples to Whisper's 16 kHz for its own input). There is no authentication.

## Project layout

```text
main.py            entry point (calls main_flow)
main_flow/         .env, config, logging init, uvicorn, graceful shutdown
composition_root/  the only place concrete adapters are wired together (engine choice, gate)
infrastructure/    config; HTTP inbound (handler, envelope, error mapper, SSE/NDJSON encoding, NDJSON utterance decoder); Whisper engines (outbound)
application/       use-case service, ports, DTOs, application errors
domain/            the utterance value objects and domain errors
scripts/           fetch_gate_model.py (downloads the gate model; run by the deploy tool's `prepare` step)
tests/             pytest by layer, plus architecture/ (the dependency rules) and simple.py (end to end, needs a running service)
vendor/            the bundled contracts wheel
docs/              architecture, API, configuration, deployment, monitoring, requirements, security, decisions
```

Dependencies point inward only (`infrastructure -> application -> domain`); `tests/architecture/` enforces this. The same layered layout as the other OBLIVION services ([ADR-001](docs/decisions/ADR-001-layered-architecture.md)).

## Test

```powershell
& windows\Scripts\python.exe -m pytest        # unit + architecture tests: no model, no network, no hardware
& windows\Scripts\python.exe tests\simple.py  # end to end against a running service (needs real audio)
```

Result on 2026-11-05: `90 passed` in about 3 s. `ruff`, `mypy` and `black` are configured in `pyproject.toml` but are **not installed in this venv**; the microphone venv's ruff reported 9 findings (4 auto-fixable) here on 2026-10-01, not fixed on purpose; mypy was not run. The real engines (OpenAI call, faster-whisper model) and `tests/simple.py` were not run in this pass.

## Scope

- **In scope:** transcribe finished utterances; serve the text as `contracts.stream` events; the optional wake-phrase gate.
- **Out of scope:** silence detection and cutting audio (microphone), deciding what the text means or who answers (Brain), calling other services (Brain is the only coordinator), converting audio between services.
- **Non-goals:** storing audio or text, speaker identification, translation.

## Known limitations

- The local model (`small.en`, English only), the compute type (`int8`) and the thread count (2) are constants: `STT_LANGUAGE=es` cannot work with the local engine. Planned: settings (see [docs/deployment_audit/stt.md](docs/deployment_audit/stt.md)).
- In a container nothing persists the Hugging Face cache, and the deploy `prepare` step has no settings at build time, so a local model downloads again on every new container.
- The shared stream is one queue: each text event is delivered once, to whoever reads it first (Brain is the only reader).
- A failure while a `set` upload is processed (bad event, not mono, an engine error) reaches Brain as an `error` event on `get`; the ack of the `set` request still ends with `input_completed`. The contract tests of the ack use a fake service that propagates the failure, so they do not show this (probed against the real service on 2026-11-05).
- No authentication, no request size limit: anyone who can reach the port can send audio (to a paid API when the engine is OpenAI).
- pytest, ruff, black and mypy are in the runtime requirement files, so they are installed in the deployed image.
- The real engines and the end-to-end script were not run in the last pass; the retest of the whole service is pending.

## Documentation

| Document | Content |
|---|---|
| [docs/architecture/architecture.md](docs/architecture/architecture.md) | Layers, flows, wire contract, decisions at a glance, known debt |
| [docs/api/api.md](docs/api/api.md) | Routes, events, status codes and errors |
| [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md) | Every variable, its default and who reads it |
| [docs/deployment/deployment.md](docs/deployment/deployment.md) | How the deploy tool runs this service, models, Docker issues |
| [docs/operations/monitoring.md](docs/operations/monitoring.md) | Probes, shutdown, logs, files on disk |
| [docs/security/security.md](docs/security/security.md) | What is implemented, what is not, what leaves the machine |
| [docs/requirements/requirements.md](docs/requirements/requirements.md) | Functional and non-functional requirements with their status |
| [docs/decisions/](docs/decisions/) | Architecture decision records (ADR-001 to ADR-007) |
| [docs/deployment_audit/stt.md](docs/deployment_audit/stt.md) | The deployment audit of 2026-11-04 (a record) |
| [docs/old/](docs/old/) | The previous layout and the removed autoloader (history, not current) |
| [CLAUDE.md](CLAUDE.md) | Rules for working in the repository, including the mandatory update of the documentation with every change |
