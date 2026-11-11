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

Working, needs a retest after the recent changes. The code and the unit tests agree (152 passed). The OpenAI engine, the local engine and the gate were run for real on a Windows PC on 2026-11-06 (see the table); Docker on amd64 was run on 2026-11-09 (T-03); a Raspberry Pi has not been run (postponed by the maintainer until everything works on Windows).

| Area | State |
|---|---|
| Shared stream: `POST /process/stream/set`, `GET /process/stream/get`, `POST /stop` | Built, covered by tests with fake engines |
| Single-request stream `POST /process/stream` and `POST /process/batch` | Built, covered by tests |
| OpenAI engine (`whisper-1`, optional `STT_PROMPT`) | Built; the real API was called on 2026-11-06 (T-01.1.4): spoken English transcribed exactly, about 0.7 to 1.5 s per utterance from a Windows PC; a wrong key gives the fixed message `OpenAI request failed: AuthenticationError (HTTP 401)` (T-01.7, 2026-11-06) |
| Local engine (faster-whisper on the CPU) | Built; run for real on 2026-11-06 on a Windows PC (`small.en` downloaded, loaded and transcribed spoken English; about 4.5 to 5 s per utterance there; **not** run on a Raspberry Pi or in Docker). Model, threads and compute type are settings (`STT_MODEL`, `STT_THREADS`, `STT_COMPUTE_TYPE`, built in T-01.2.3 and unit-tested with a fake model; a non-default value was **not** run with a real model) |
| Wake-phrase gate under `/gate/...` (`STT_GATE_ENABLED=1`) | Built, covered by tests with fake engines; the real `tiny.en` gate returned the spoken wake phrase with the utterance audio in under 1 s on 2026-11-06 (Windows PC). Through Brain with a real microphone on 2026-11-09 the path worked (no phrase: no batch request; phrase: exactly one), but the gate (then `tiny.en` with the prompt `Oblivion`) heard the name only 1 time in 4. Tuned the same day offline on 16 real clips: since then the defaults are `STT_GATE_MODEL=base` and `STT_GATE_PROMPT=Oblivion 306.` (8 of 10 phrases caught offline, 0 of 6 ordinary sentences, 0.6 s per clip on a PC). **Re-run live the same day: only 2 of 8 phrases were accepted** (3 ordinary sentences ignored correctly); the cause was found the same day: the microphone service started each utterance 0.01 to 0.12 s after the voiced onset and clipped the first sounds of the name. After a pre-roll was added to the microphone (`MICROPHONE_PREROLL_SECONDS`, 0.2 s) a third live run accepted **4 of 4** phrases that reached the gate (6 other utterances were dropped by Brain's echo guard while the robot was speaking; small sample, ADR-005). Not run on a Pi |
| `contracts` events, envelope, error mapping | Built (contracts 0.16.0 wheel in `vendor/`, committed in `8ee7c7d`, not pushed) |
| Silence detection | **Not here by design**: it lives in `microphone_microservice` |
| Authentication, CORS, request size limit | **Not built** (see [docs/security/security.md](docs/security/security.md)) |
| Docker image | None in this repo: `deployment/` builds it. Built and run on amd64 on 2026-11-09 (865 MB, Python 3.12): the models live on the volume `oblivion-stt-models` ([ADR-009](docs/decisions/ADR-009-model-delivery-in-docker.md)) and a recreated container does not download again; runs as root; arm64 not run (see [docs/deployment/deployment.md](docs/deployment/deployment.md)) |

## Requirements

- Python 3.14 in the service venv `windows\Scripts\python.exe` (the deployment Docker image uses 3.12; `pyproject.toml` targets 3.11). The runtime packages are pinned to the versions the engines ran with (Python 3.12 or newer; on 3.11 `numpy` falls back to an open bound, not proven).
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
| `STT_ENGINE` | `openai` | `openai` = Whisper API (`whisper-1`); any other value (for example `local`) = local faster-whisper (on the CPU; the model, threads and compute type are settings, see below). Case-insensitive |
| `STT_LANGUAGE` | `en` | ISO-639-1 code forced on the transcription (empty falls back to `en`) |
| `STT_PROMPT` | empty | OpenAI engine only: words the model should spell as written (for example `Oblivion 306`) |
| `STT_MODEL` | `small.en` | Model of the local engine (the default is English only; a multilingual one such as `small` for other languages, with `STT_LANGUAGE`) |
| `STT_THREADS` | `2` | CPU threads of every local model, the gate's too; `0` = let ctranslate2 choose; a bad value stops the start |
| `STT_COMPUTE_TYPE` | `int8` | Compute type of every local model (`int8`, `float32`...) |
| `STT_GATE_ENABLED` | `0` | `1` = also run the wake-phrase gate under `/gate/...` |
| `STT_GATE_MODEL` | `base` | faster-whisper model of the gate (greedy decoding); multilingual, `tiny.en` is faster and misses the name more often, `small.en` is more exact and slower |
| `STT_GATE_PROMPT` | `Oblivion 306.` | Hint so the gate spells the wake phrase right: give it the name and the code (empty = none) |
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
composition_root/  the only place concrete adapters are wired together: one file per object in dependencies/ (the engine, the gate's engine, the service, the HTTP app) and the container
infrastructure/    config; HTTP inbound: http_handler.py (wires the endpoints) with routes/ (one file per endpoint), response/ (envelope, SSE/NDJSON framing), errors/ (error to status) and helpers/ (request decoding); Whisper engines (outbound)
application/       use-case service, three ports (service, inbound, outbound), DTOs in inbound/ and outbound/, application errors
domain/            the utterance value objects and domain errors
scripts/           fetch_gate_model.py (downloads the local models the settings need: the main model when the engine is local, the gate's when the gate is on; run by the deploy tool's `prepare` step; the name is kept because the deploy catalogue names it)
tests/             pytest by layer, plus architecture/ (the dependency rules), scripts/ (the deploy `prepare` script) and simple.py (end to end, needs a running service)
vendor/            the bundled contracts wheel
requirements.*.txt requirements.windows.txt and requirements.linux.txt (what the service runs on; the deploy tool installs them); requirements.dev.txt (tests and lint; the tool never installs it)
docs/              architecture, API, configuration, deployment, monitoring, requirements, security, decisions, tasks, questionnaires
```

Dependencies point inward only (`infrastructure -> application -> domain`); `tests/architecture/` enforces this. The same layered layout as the other OBLIVION services ([ADR-001](docs/decisions/ADR-001-layered-architecture.md)).

## Test

```powershell
& windows\Scripts\python.exe -m pip install -r requirements.dev.txt   # once: pytest, httpx, ruff, black, mypy
& windows\Scripts\python.exe -m pytest        # unit + architecture tests: no model, no network, no hardware
& windows\Scripts\python.exe tests\simple.py  # end to end against a running service (needs real audio)
```

Result on 2026-11-11: `152 passed` in about 3 s (140 on 2026-11-08; 9 new ones check that the service, the HTTP handler and both engines implement their ports and 3 that every DTO sits in `application/dtos/inbound` or `outbound`). The workspace pipeline check on the same day gave `63 passed, 18 skipped, 21 failed`: the failures are the brain to ai-agent flow tests and ai-agent's bundled-wheel check, none involve stt (its pipeline tests pass). Result on 2026-11-08: `140 passed` in about 3 s (90 on 2026-11-05; T-01.7 added 5 tests, T-01.2.2 added 11, T-01.2.3 added 6, and T-01.3.1 and T-01.3.2 added 28 for the deploy `prepare` script). On 2026-11-06 the same 90 passed in a clean clone of the pushed branch (T-01.1.1, 6.7 s), and the workspace pipeline check (`brain_microservice\windows\Scripts\python.exe -m pytest contracts\tests -q` from the workspace root, stt as a fake engine behind the real handler) gave `84 passed, 18 skipped` in 82 s (T-01.1.6; the skips are the real-LLM tests and requirement files a service does not have). `ruff`, `mypy` and `black` are configured in `pyproject.toml` but are **not installed in this venv**; the microphone venv's ruff reported 9 findings (4 auto-fixable) here on 2026-10-01, not fixed on purpose; mypy was not run. The real engines (OpenAI call, faster-whisper model) and `tests/simple.py` were not run in this pass.

## Scope

- **In scope:** transcribe finished utterances; serve the text as `contracts.stream` events; the optional wake-phrase gate.
- **Out of scope:** silence detection and cutting audio (microphone), deciding what the text means or who answers (Brain), calling other services (Brain is the only coordinator), converting audio between services.
- **Non-goals:** storing audio or text, speaker identification, translation.

## Known limitations

- In a container the Hugging Face cache lives on the named volume `oblivion-stt-models`, filled by `prepare` run once in a throw-away container ([ADR-009](docs/decisions/ADR-009-model-delivery-in-docker.md)); verified on amd64 on 2026-11-09 (a recreated container does not download again). With an empty volume and no network the container crash-loops; the container runs as root; arm64 was not run (the OpenAI engine did run inside the container).
- The shared stream is one queue: each text event is delivered once, to whoever reads it first (Brain is the only reader).
- A failure while a `set` upload is processed (bad event, not mono, an engine error) reaches Brain as an `error` event on `get`; the ack of the `set` request still ends with `input_completed`. The contract tests of the ack use a fake service that propagates the failure, so they do not show this (probed against the real service on 2026-11-05).
- Only the seven packages the service imports are pinned; the packages they depend on are not (no lock file), and nothing scans the dependencies.
- No authentication, no request size limit: anyone who can reach the port can send audio (to a paid API when the engine is OpenAI).
- A Raspberry Pi has not been run (postponed); Docker ran on amd64 on 2026-11-09. The local engine, the gate and the OpenAI engine were run for real on a Windows PC on 2026-11-06 (T-01.1.2 to T-01.1.4 of [docs/tasks](docs/tasks/README.md)); `tests/simple.py` ran against it and only checks `/health` and `/available` (on a Windows console it needs `python -X utf8`, or it fails printing its box characters). The retest of the whole service is pending.

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
| [docs/decisions/](docs/decisions/) | Architecture decision records (ADR-001 to ADR-009) |
| [docs/deployment_audit/stt.md](docs/deployment_audit/stt.md) | The deployment audit of 2026-11-04 (a record) |
| [docs/tasks/](docs/tasks/README.md) | The deployment task plan of 2026-11-06 (epics T-01 to T-04, [order](docs/tasks/ORDER.md)) |
| [docs/questionnaires/](docs/questionnaires/00_README.md) | Questions only the maintainer can answer (Q01: the decisions and facts the task plan needs) |
| [docs/old/](docs/old/) | The previous layout and the removed autoloader (history, not current) |
| [CLAUDE.md](CLAUDE.md) | Rules for working in the repository, including the mandatory update of the documentation with every change |
