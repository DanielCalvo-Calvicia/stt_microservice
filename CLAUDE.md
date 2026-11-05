# CLAUDE.md: stt_microservice

Port **8001** (`SERVICE_PORT`). Python/FastAPI. Speech to text: it turns finished utterances (16-bit mono PCM) into text with the OpenAI Whisper API or a local faster-whisper model, and has an optional wake-phrase gate. Read [README.md](README.md) for the state and the endpoints, [docs/architecture/architecture.md](docs/architecture/architecture.md) for the structure and `../CLAUDE.md` for the workspace rules.

Current state (2026-11-05): branch `feature_ai_claude_2` (tracks `origin/feature_ai_claude_2`), last feature commit `853d1bf` "Bundle contracts 0.15.0". Status: working, needs retest after recent changes. Tests: `90 passed` (2026-11-05, about 3 s, no model, no network). Ruff/mypy are not installed in this venv (the microphone venv's ruff reported 9 findings here on 2026-10-01, unfixed). The real engines (OpenAI call, faster-whisper model) and `tests/simple.py` were not run in the last documentation pass.

## MANDATORY: every change updates the documentation

**No change is finished until the documents that describe it are true again.** This applies to every change: code, configuration, tests, a decision. Do it in the same piece of work, not later. A change that leaves a document saying something false is not done.

| If you change... | Update, in the same change |
|---|---|
| A file, a folder or a class name, or a layer rule | the layout of [README.md](README.md) and [docs/architecture/architecture.md](docs/architecture/architecture.md) (sections 2 and 3), and `tests/architecture/` if a rule moves |
| An environment variable, a default or a setting | `.env.example`, the tables of [README.md](README.md), [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md), and (another repo) `deployment/config/services/stt.toml` through `deployment\scripts\env_inventory.py --write` and the stt table of `deployment/docs/DEPLOYMENT.md` |
| A route, a request or response shape, a status code or an event | [docs/api/api.md](docs/api/api.md), [docs/requirements/requirements.md](docs/requirements/requirements.md), the table of [README.md](README.md) and the tests; a new event goes into `contracts` first (see the rules below) |
| Logging, probes, shutdown, files on disk, what is sent to a third party | [docs/operations/monitoring.md](docs/operations/monitoring.md) and [docs/security/security.md](docs/security/security.md) |
| A requirement (new, changed, done) | [docs/requirements/requirements.md](docs/requirements/requirements.md) (status of the row) and the status table of [README.md](README.md) |
| A decision (an engine, a contract, a boundary between services) | an ADR in `docs/decisions/` (new, or a dated update of the one it changes) and the list in the architecture document, section 6 |
| A risk, a limit, a known debt | the *Known limitations* of [README.md](README.md) and the *Known debt* of the architecture document; [docs/security/security.md](docs/security/security.md) if it is a security one |
| The dependencies, the contracts wheel, the Python version, the deploy `prepare` step | [docs/deployment/deployment.md](docs/deployment/deployment.md), `requirements.*.txt` and the version named in this file |
| The test count, the date of a run, what was or was not run | the *Test* section of [README.md](README.md) and the *Current state* line above |

How to do it:
1. Change the documents **with** the change, and say what you updated when you report the work.
2. Use dated notes (`> **Update 2026-11-05:** ...`) in documents that are history (ADRs, the audit in `docs/deployment_audit/`); correct the text in documents that describe the present (requirements, architecture, README, API, configuration, monitoring, security, deployment).
3. Mark what is planned as **Planned** and what is built as **Built**; never describe as working something that was not run. The real engines and the hardware-dependent parts have not been run recently: say so.
4. After editing, check that the links still resolve and that every path named in a document exists.
5. When the documents and the code disagree and you cannot tell which is right, do not guess: ask the maintainer.

## Role

Brain feeds it finished utterances and reads the text back. STT does **no** silence detection: the microphone service cuts the audio (silence detection moved there, each treatment is a `MICROPHONE_*` env var) and STT transcribes each utterance as one batch.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads NDJSON events (`STT_INBOUND`: `stream_started`, one `utterance` per utterance; a `completed` that carries audio counts as one more). A body that is not NDJSON is a 415. Answers with an ack stream that ends in `input_completed` or `error` |
| `GET /process/stream/get` | Brain reads text events (SSE, or NDJSON with `Accept`); heartbeat every 15 s; 404 if nothing was set |
| `POST /process/stream` | Single-request variant (NDJSON `utterance` events in the body, answers SSE). No query settings |
| `POST /process/batch?sample_rate=` | One PCM buffer -> `data: {text}`; 400 on an empty body |
| `/gate/process/stream/{set,get}` | Only with `STT_GATE_ENABLED=1`: the wake-phrase gate, a second local faster-whisper (`STT_GATE_MODEL`, default `tiny.en`, greedy, `STT_GATE_PROMPT` as hint) with its own shared stream. Its `completed` events carry the utterance audio in `audio_base64` (contracts 0.11.0). Brain decides from the text; the real STT only gets `/process/batch` with that audio |
| `GET /health`, `/available`, `POST /stop` | Liveness, engine readiness, stop |

Errors: 404 no stream set, 415 body that is not NDJSON, 422 invalid utterance (only when it is raised before the stream starts), 400 empty batch body, else 500. A failure after a stream has started is an `error` event in the stream, not a status. Full detail: [docs/api/api.md](docs/api/api.md).

Engines: `STT_ENGINE=openai` (default, Whisper API `whisper-1`, needs `OPENAI_API_KEY`) or any other value, such as `local` (faster-whisper `small.en`, CPU, int8, 2 threads: constants in `local_whisper_transcription.py`, not settings). `STT_LANGUAGE` forces the language (default `en`). Other env: `SERVICE_NAME/HOST/PORT`, `LOG_LEVEL`, `STT_PROMPT`. A `.env` next to `main.py` is loaded by `main_flow/http.py`. All variables: [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md).

## Layout

`main.py` -> `main_flow/` -> `composition_root/` -> `application/` -> `domain/` -> `infrastructure/`. Dependencies point inward only and `tests/architecture/` enforces it. The `input_completed` ack event lives in `contracts.stream.common.input_completed`.

## Rules

- Events use `contracts.stream` (`STT_INBOUND`/`STT_OUTBOUND`, `UPLOAD_ACK`) and the shared codec. Never hand-write event JSON.
- The old autoloader (direct pull from another service's stream) was removed on purpose (archived in `docs/old/autoloader/`). Do not reintroduce direct service-to-service calls. Brain coordinates.
- Never log or echo `OPENAI_API_KEY`. Do not open `.env`. Do not log the text or the audio of an utterance (the service logs lengths only).
- `contracts` comes from `vendor/contracts_microservice-<version>.whl` (0.15.0); refresh it with `contracts/scripts/bundle.py`.
- Ruff/mypy/black are configured in `pyproject.toml` but not installed in this venv, and they are listed in the runtime requirement files (known debt, see the architecture document). Install them first if you need them, and do not bulk-fix lint unasked.
- `.engram/` holds old notes. Do not trust it over the code. `docs/deployment_audit/stt.md` is the audit of 2026-11-04 (a record, not the source of truth).
- Do not commit or push unless asked.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest        # about 3 s, no model, no network
```
