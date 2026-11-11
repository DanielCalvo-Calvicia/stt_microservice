# CLAUDE.md: stt_microservice

Port **8001** (`SERVICE_PORT`). Python/FastAPI. Speech to text: it turns finished utterances (16-bit mono PCM) into text with the OpenAI Whisper API or a local faster-whisper model, and has an optional wake-phrase gate. Read [README.md](README.md) for the state and the endpoints, [docs/architecture/architecture.md](docs/architecture/architecture.md) for the structure and `../CLAUDE.md` for the workspace rules.

Current state (2026-11-11): branch `feature_ai_claude_2` (tracks `origin/feature_ai_claude_2`), HEAD `8ee7c7d` (2026-11-09: deployment readiness, Docker model volume, gate defaults, task plan and documents, with the `contracts` 0.16.0 wheel) on top of `bcd76a0` (documentation restructure); both are committed and **not pushed** (2 ahead of origin). The working tree holds the uncommitted restructure of 2026-11-11: three ports (`SttServicePort`, `SttInboundPort`, `SttOutboundPort`), DTOs split into `inbound/` and `outbound/`, one dependency file per object, the inbound HTTP folder split into `routes/`, `response/`, `errors/` and `helpers/`, and the removal of `.engram/` and the empty `domain/operations/`. The committed wheel is 0.16.0; the venv `windows` still has `contracts` 0.15.0 installed (not reinstalled; the tests pass with it). Status: working, needs retest after recent changes. Tests: `152 passed` (2026-11-11, about 3 s, no model, no network; 90 before T-01.7, T-01.2.2, T-01.2.3, T-01.3.1 and T-01.3.2). The workspace pipeline check on 2026-11-11 gave `63 passed, 18 skipped, 21 failed`: the failures are the brain to ai-agent flow tests and ai-agent's bundled-wheel check (its wheel is 0.15.0), none involve stt; `contracts/tests/e2e/fake_services.py` was edited (uncommitted, in the `contracts` repo) for the `SttOutboundPort` rename. Ruff/mypy are not installed in this venv (the microphone venv's ruff reported 9 findings here on 2026-10-01, unfixed). The local engine, the gate and the OpenAI engine were run for real on a Windows PC on 2026-11-06 (T-01.1.2 to T-01.1.4: models downloaded, spoken English transcribed, `tests/simple.py` passed its two checks with `python -X utf8`); the failure drills ran on 2026-11-06 (T-01.1.5); the wake-phrase round trip through Brain ran with a real microphone on 2026-11-09 (T-01.1.7: the path works; the gate then heard the name 1 time in 4, so the gate defaults became `base` and `Oblivion 306.` on 2026-11-09, tuned offline on 16 real clips and not re-run live); a Raspberry Pi and Docker was run on amd64 on 2026-11-09 (T-03.1 to T-03.5: the image, the volume `oblivion-stt-models`, a restart and a recreate without a download; the OpenAI engine ran inside the container too); a Raspberry Pi has not been run (postponed by the maintainer until everything works on Windows).

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
3. Mark what is planned as **Planned** and what is built as **Built**; never describe as working something that was not run. The OpenAI engine, the local engine and the gate were run for real on a Windows PC on 2026-11-06; a Raspberry Pi, Docker and anything that needs hardware have not been run: say so.
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
| `/gate/process/stream/{set,get}` | Only with `STT_GATE_ENABLED=1`: the wake-phrase gate, a second local faster-whisper (`STT_GATE_MODEL`, default `base`, greedy, `STT_GATE_PROMPT`, default `Oblivion 306.`, as hint) with its own shared stream. Its `completed` events carry the utterance audio in `audio_base64` (contracts 0.11.0). Brain decides from the text; the real STT only gets `/process/batch` with that audio |
| `GET /health`, `/available`, `POST /stop` | Liveness, engine readiness, stop |

Errors: 404 no stream set, 415 body that is not NDJSON, 422 invalid utterance (only when it is raised before the stream starts), 400 empty batch body, else 500. A failure after a stream has started is an `error` event in the stream, not a status. Full detail: [docs/api/api.md](docs/api/api.md).

Engines: `STT_ENGINE=openai` (default, Whisper API `whisper-1`, needs `OPENAI_API_KEY`) or any other value, such as `local` (faster-whisper on the CPU: `STT_MODEL` default `small.en`, `STT_THREADS` default 2, `STT_COMPUTE_TYPE` default `int8`; the gate shares the threads and the compute type, ADR-008). `STT_LANGUAGE` forces the language (default `en`). Other env: `SERVICE_NAME/HOST/PORT`, `LOG_LEVEL`, `STT_PROMPT`. A `.env` next to `main.py` is loaded by `main_flow/http.py`. All variables: [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md).

## Layout

`main.py` -> `main_flow/` -> `composition_root/` -> `infrastructure/` -> `application/` -> `domain/`. Dependencies point inward only and `tests/architecture/` enforces it. The `input_completed` ack event lives in `contracts.stream.common.input_completed`.

- **Ports** (`application/ports/`, one folder each): `service/` `SttServicePort` (the use cases, `SttService` implements it), `inbound/` `SttInboundPort` (what every inbound adapter offers, `SttHandler` implements it), `outbound/` `SttOutboundPort` (what every engine offers). A new inbound or outbound adapter implements its port. `tests/architecture/test_ports.py` checks it.
- **DTOs** are in `application/dtos/inbound/` (requests) or `application/dtos/outbound/` (responses), never loose (`test_dtos.py`).
- **Inbound HTTP adapter** (`infrastructure/inbound/http/`, laid out like `dynamics_microservice`): `http_handler.py` only wires endpoints to `routes/` (one file per endpoint); `response/`, `errors/` and `helpers/` hold the answers, the error mapping and the request decoding. `helpers` is allowed as a folder name only there.
- **Composition root:** one file per object in `composition_root/dependencies/` (the engine, the gate's engine, the service, the HTTP app).

## Rules

- Events use `contracts.stream` (`STT_INBOUND`/`STT_OUTBOUND`, `UPLOAD_ACK`) and the shared codec. Never hand-write event JSON.
- The old autoloader (direct pull from another service's stream) was removed on purpose (archived in `docs/old/autoloader/`). Do not reintroduce direct service-to-service calls. Brain coordinates.
- Never log or echo `OPENAI_API_KEY`. Do not open `.env`. Do not log the text or the audio of an utterance (the service logs lengths only).
- `contracts` comes from `vendor/contracts_microservice-<version>.whl` (0.16.0, committed in `8ee7c7d`); refresh it with `contracts/scripts/bundle.py`.
- Ruff/mypy/black are configured in `pyproject.toml` and listed, with pytest and httpx, in `requirements.dev.txt` (install it on top of the runtime file; the deploy tool never installs it). They are not installed in this venv: install them first if you need them, and do not bulk-fix lint unasked.
- `docs/deployment_audit/stt.md` is the audit of 2026-11-04 (a record, not the source of truth).
- Do not commit or push unless asked.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pip install -r requirements.dev.txt   # once: pytest, httpx and the lint tools
& windows\Scripts\python.exe -m pytest        # about 3 s, no model, no network
```
