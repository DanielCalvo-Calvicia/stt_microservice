# Tasks

Hierarchical task plan to make the **new deployment of `stt_microservice`** work and prove it: **T-01 deployment readiness of the service, T-02 changes in the deployment tool (the `deployment` repository), T-03 Docker and arm64 acceptance, T-04 documentation sync**. It was generated on 2026-11-06 from the deployment audit ([../deployment_audit/stt.md](../deployment_audit/stt.md)), and every claim it relies on was read in the code or run on 2026-11-06 (section 4). It is written to be executed step by step by the assistant: every leaf task states what to change, what it must not do, and how to prove it is done.

The status of every task is on the board in section 5. The order in which to do them, with state and date, is in [ORDER.md](ORDER.md) (kept in step with the board and with every task file).

**Plan revision 1 (2026-11-06):** first version. No code task is done. One decision stops part of the chain: [T-02.1](T-02_deployment-tool-changes/T-02.1_model-delivery-decision.md) (how the models reach a container) is `awaiting-user`; the tasks that depend on it are `blocked`.

**Plan revision 2 (2026-11-06):** the maintainer answered [T-01.2.1](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.1_settings-decision.md) (option A: `STT_MODEL`, `STT_THREADS`, `STT_COMPUTE_TYPE`, shared by the main model and the gate; a bad `STT_THREADS` stops the start; the compute type is passed through). T-01.2.2, T-01.2.3, T-01.3.2, T-01.5 and T-03.6 are now `todo`; T-01.2.2 also writes ADR-008.

**Plan revision 3 (2026-11-06):** the maintainer answered [Q01](../questionnaires/Q01_before-the-deployment-tasks.md). [T-02.1](T-02_deployment-tool-changes/T-02.1_model-delivery-decision.md) is decided (**option B**: the volume `oblivion-stt-models`, the run-time `prepare`, a failed download is a warning, the volume is never deleted automatically; [ADR-009](../decisions/ADR-009-model-delivery-in-docker.md)), so no decision is open and nothing is `blocked` any more: T-02.2 to T-02.5 and T-03.1 to T-03.8 are `todo` (waiting only on their dependencies). New task [T-01.6](T-01_deployment-readiness/T-01.6_pin-runtime-dependencies.md) (pin the runtime dependencies after the real engines have run). Also recorded: Spanish is planned for the future (tests with a multilingual model in T-01.2.2 and T-01.2.3, a Spanish measurement in T-03.6); the Pi is a 4B with 4 GB, 64-bit Raspberry Pi OS without a desktop; the `contracts` 0.16.0 edit is the maintainer's and stays; limits and timeouts (NFR-8) stay documented debt; the assistant stays inside stt and `deployment` and does not touch Brain's preflight unless the measured time proves `prepare` is not enough; the engine of the real robot is undecided (OpenAI stays the default; T-01.1.3 and T-03.6 give the numbers); there is no time limit (`UNKNOWN`), so the tasks report times only.

**Plan revision 4 (2026-11-06):** new task [T-01.7](T-01_deployment-readiness/T-01.7_hide-openai-error-text.md) (the OpenAI engine raises a fixed message so a wrong key is not echoed in part), found by the failure drills of T-01.1.5 and added at the maintainer's yes. No other change.

> **Note 2026-11-11:** the task files are records of the time they were written. The code paths they name have moved since: `composition_root/dependencies/stt_dependencies.py` is now four files (`transcription_dependency.py`, `gate_transcription_dependency.py`, `stt_service_dependency.py`, `http_app_dependency.py`); `TranscriptionPort` (`application/ports/outbound/transcription_port.py`) is `SttOutboundPort` (`stt_outbound_port.py`); `SttTranscriptionPort` is `SttServicePort` (`application/ports/service/`); the DTOs are in `application/dtos/inbound/` and `outbound/`; the files of `infrastructure/inbound/http/` are in its `routes/`, `response/`, `errors/` and `helpers/` subfolders. The current layout is in [../architecture/architecture.md](../architecture/architecture.md) section 3.

## 1. Structure and naming

- Every task is a Markdown file. A task with subtasks lives in a folder of the same name, and its own file has the same name inside that folder. Leaves are single files.
- IDs are hierarchical and stable: `T-01` → `T-01.2` → `T-01.2.3`. Never reuse or renumber an ID.
- A parent task describes goal, order and exit criteria; **leaves carry the detail**.
- Every task file starts with the same header table (`Status`, `Kind`, `Parent`, `Depends on`, `Blocks`, `Size`) and has the sections *Goal*, *Read first*, *Files*, *Specification* or *Steps*, *Acceptance criteria*, *Verification* and *Notes*.

```
docs/tasks/
├── README.md                                   (this file)
├── ORDER.md                                    the order, the state and the date of every task
├── T-01_deployment-readiness/                  epic 1 (this repository)
│   ├── T-01_deployment-readiness.md
│   ├── T-01.1_baseline-checks/                 group with its leaves (no code change)
│   ├── T-01.2_local-model-settings/            group: STT_MODEL, STT_THREADS, STT_COMPUTE_TYPE
│   ├── T-01.3_model-download-step/             group: the `prepare` script
│   ├── T-01.4_requirements-split.md            leaf directly under T-01
│   ├── T-01.5_service-documents.md
│   ├── T-01.6_pin-runtime-dependencies.md
│   └── T-01.7_hide-openai-error-text.md
├── T-02_deployment-tool-changes/               epic 2 (the `deployment` repository)
├── T-03_docker-and-arm64-acceptance/           epic 3
└── T-04_documentation-sync.md                  recurring
```

Kinds: `code`, `test`, `decision`, `docs`, `manual` (needs a real machine, a real device, a download, a paid API call or a person: the assistant prepares the commands and says what to look at; the maintainer runs it, or the assistant runs it after the maintainer says so). `stt` uses no hardware of its own; its manual tasks need a network, a model download, an OpenAI key, a Raspberry Pi, or (T-01.1.7) the real microphone through Brain. Anything that would move the stepper motors is out of this plan; if a run through Brain could, **ask before moving**.

## 2. Execution protocol (how the assistant works through this plan)

1. Pick the first task whose status is `todo` and whose `Depends on` tasks are all `done`. A decision (`decision`) that is `awaiting-user` **stops the chain** for the tasks that depend on it: ask the user, record the answer in the task's *Notes*, then continue.
2. Read the files listed in the task's *Read first*, and the `CLAUDE.md` of the repository you are about to edit (`stt_microservice` here, including its rule that every change updates its documents; `deployment/CLAUDE.md` for T-02).
3. Create or modify only the files listed under *Files* (tests included). Another file, dependency or folder requires updating the task first.
4. Implement, then run the task's *Verification* and the baseline of section 3. A task is `done` only when every acceptance criterion passes.
5. Set the task's `Status` to `done`, update its row on the board (section 5) and in [ORDER.md](ORDER.md), update the parent if its exit criteria are met, and record any new fact or deviation in the task's *Notes*.
6. Update the documents the change touches, in the same piece of work (table in `CLAUDE.md` of the repository).
7. Do not commit, push or publish unless the user asks. Do not run anything that deploys, builds an image, downloads a model, calls the OpenAI API or reaches another machine without saying so first (`deploy`, `docker build`, `fetch_gate_model.py` with a local engine, anything with `--remote`) and waiting for a yes. **Standing permission (Q01-12, 2026-11-06):** the maintainer allows the assistant to run each manual task, one at a time, as soon as the maintainer says "go" for that task, using the files the maintainer already keeps in `deployment/config/local/`; the key is never printed or copied. "Go" is still needed per task, and nothing that moves a motor is covered.
8. Never open a `.env` file (the service folder has a real one) and never print a key. `oblivion.py env` masks secrets; use it to look at settings.

Status values: `todo` (ready once its dependencies are done), `awaiting-user` (a decision needs an answer), `blocked` (waits, directly or through other tasks, for such a decision), `in-progress`, `done`, `postponed` (decided not to run yet; it does not block the Windows work).

## 3. Baseline definition of done (applies to every code or test task)

- `windows\Scripts\python.exe -m pytest` passes from `stt_microservice` (**90 passed** on 2026-11-06; a task that adds tests raises the number, and the new count goes into the documents that name it: the *Test* section of `README.md` and the *Current state* line of `CLAUDE.md`).
- Tests live under `tests/`, mirroring the layer they cover (`application`, `domain`, `infrastructure`, `composition_root`, `architecture`; a new `tests/scripts/` for the files in `scripts/`); they need no model download, no network, no OpenAI call and no hardware (fakes, `tmp_path`, `monkeypatch`: the local engine is faked by replacing `WhisperModel` in `local_whisper_transcription`, as `tests/infrastructure/test_transcription_engines.py` does). The test folders have no `__init__.py` and `pytest.ini` uses `--import-mode=importlib`: do not add `__init__.py` files. `tests/architecture/test_dependency_rules.py` stays green: dependencies point inward only.
- Logging only through `shared_logging` (`get_logger(__name__)`), constant message strings with keyword fields; never stdlib `logging`. Never log the text or the audio of an utterance, or `OPENAI_API_KEY`.
- Settings only from environment variables, documented in `.env.example`; after any `.env.example` change run `brain_microservice\windows\Scripts\python.exe deployment\scripts\env_inventory.py --write` from the workspace root (that writes in the `deployment` repository: read its `git status` first, F14).
- No change in `contracts` is needed by this plan (F15). If a task discovers it needs one (a field or an event other services see), contracts goes first, with a version bump, then every service re-bundles it.
- No secrets in code, tests, fixtures or documents. Never open `.env`.
- Ruff, black and mypy are configured in `pyproject.toml` but not installed in this venv: do not bulk-fix lint unasked. Keep the line endings of the file you edit.
- Use the service venv (`windows\Scripts\python.exe`), not a global Python. Search only inside the service and exclude `windows/` and the cache folders (`.mypy_cache`, `.pytest_cache`, `.ruff_cache`). Never grep the whole workspace.
- The documents the change touches are updated in the same change (table in `CLAUDE.md`: environment variable, deployment/dependencies, requirement, debt/limitation, decision, test count): this is part of done. Check that the links in them still resolve.

## 4. Facts the tasks rely on

Verified on 2026-11-06 against the code of both repositories (read, `[C]`) or by running something (`[D]`), unless a row says otherwise. Nothing was deployed, built or downloaded.

| # | Fact |
|---|---|
| F1 | The stt repository is on branch `feature_ai_claude_2`; the last commit is `bcd76a0` "Restructure the documentation like dynamics_microservice" (before it `853d1bf` "Bundle contracts 0.15.0"). The working tree has uncommitted edits that are **not part of this plan**: `requirements.windows.txt` and `requirements.linux.txt` name `contracts_microservice-0.16.0-py3-none-any.whl`, the 0.15.0 wheel in `vendor/` is deleted and the 0.16.0 one is untracked. The documents still say 0.15.0. `pytest`: **90 passed** (`[D]`). |
| F2 | `requirements.windows.txt` and `requirements.linux.txt` are identical: fastapi, uvicorn, python-dotenv, pydantic, numpy, openai, faster-whisper, httpx, **pytest**, **ruff**, **black**, **mypy**, `-e ../shared-logging`, the vendored contracts wheel. `httpx` is imported only by tests (`tests/infrastructure/test_gate_http.py`); no file of the service imports it (`openai` depends on it anyway). T-01.4 (2026-11-08) moved httpx, pytest, ruff, black and mypy to `requirements.dev.txt`; with openai 3.x the runtime brings `httpx2`, not `httpx`. `[C]` |
| F3 | `-e ../shared-logging` points at a sibling folder, so a lone clone cannot install the file. The deployment tool strips `-e ../<sibling>` lines (`filtered_requirements` in `deployment/infrastructure/outbound/installer/native_installer.py`) and installs a wheel of the library. `[C]` |
| F4 | The local engine's model settings are constants: `DEFAULT_MODEL_NAME = "small.en"` (`infrastructure/outbound/local_whisper/local_whisper_transcription.py:18`) and `WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=2)` (line 54). `new_transcription` (`composition_root/dependencies/stt_dependencies.py:30`) passes only the language, so the main model is always `small.en`; `new_gate_transcription` passes `gate_model`, the gate prompt and `beam_size=1`, and the gate gets the same compute type and threads. `SttConfig` has no field for any of them. `[C]` |
| F5 | `scripts/fetch_gate_model.py` (the catalogue's `prepare`) does nothing and exits 0 unless `STT_GATE_ENABLED` is on; otherwise it loads `STT_GATE_MODEL` once (`device="cpu", compute_type="int8"`) and exits 0, or exits 1 on any exception. It never loaded the main model until T-01.3.2 (2026-11-08) made it fetch the main model too. No test touched it until T-01.3.1 (2026-11-08) pinned it with 17 test cases in `tests/scripts/test_fetch_gate_model.py`. `[C]` |
| F6 | `[services.stt]` in `deployment/config/catalogue.toml`: port 8001, `ready = "/available"`, `libraries = ["shared-logging"]`, `requirements` windows/linux, `prepare = ["scripts/fetch_gate_model.py"]`, `[services.stt.env] STT_ENGINE = "openai"`, `require` `OPENAI_API_KEY` when the engine is `openai`. No `apt`, no `audio` (so it can run in Docker), no `min_python`, `dotenv` default `true`. `[C]` |
| F7 | Natively, `DeploymentService.prepare` runs the script with the service's own python after the `.env` is written (deploy, update, rollback); a failure only warns. For Docker the Dockerfile runs it at **build** time (`RUN ... python $PREPARE || echo "warning: prepare step failed"`), and `docker_runtime.py` says "no .env exists yet", so the settings have their defaults (openai, gate off) and the script returns at once. `[C]` |
| F8 | The Docker runtime has **no volume support**: `docker_runtime.start` removes the container (`docker rm -f`) and starts it with `-p`, `--add-host` and, because `dotenv` is true, a read-only bind mount of the generated `.env` at `/app/.env`. A search of `deployment/` finds no `volume` or `HF_HOME` in code or catalogue. `prepare_context` copies the service folder without `.git`, `__pycache__`, `.venv`, `windows`, `.env`, `*.pyc`. The image is `python:3.12-slim-bookworm`. `[C]` |
| F9 | Runtime-specific settings have one hook: `resolve_env` in `deployment/domain/rules/env_resolution.py` sets `SERVICE_HOST` to `0.0.0.0` when `instance.runtime == "docker"` (a *computed* layer). A variable that is set but not listed in the service's `.env.example` draws a "typo?" warning unless the catalogue lists it in `extra_env` or `internal` (`domain/rules/env_names.py`); `HF_HOME` is in neither (`internal` is the catalogue key for a variable that is accepted but never advertised). `[C]` |
| F10 | `HF_HOME` written in the service's `.env` takes effect: the module `main_flow.http` imports neither `faster_whisper` nor `huggingface_hub` (nor `openai`) when loaded, and the engine module is imported inside `new_transcription` after `load_dotenv`. A scratch run with a `.env` that sets `HF_HOME` made `huggingface_hub.constants.HF_HUB_CACHE` point into that folder. `[D]` |
| F11 | The local engine loads its model in its constructor, before uvicorn starts. With an empty cache and `HF_HUB_OFFLINE=1`, `LocalWhisperTranscription()` raises `LocalEntryNotFoundError`, so the process would exit; the container's `--restart unless-stopped` would then restart it (the loop itself was **not run**). `[D]` for the exception, `[C]` for the rest. |
| F12 | `GET /available` is true when the engine is "ready" (OpenAI: the key is not empty, no network call; local: the model object exists) and, with the gate on, the gate's engine too. While a local model downloads or loads, nothing answers. `[C]` (`docs/operations/monitoring.md`, `http_handler.py:109`) |
| F13 | The deploy tool waits for `/available` for `--health-timeout` seconds (default **60**, `deployment/application/dtos/options.py`) and Brain's preflight waits `STARTUP_PREFLIGHT_TIMEOUT_SECONDS=60` (`brain_microservice/.env.example`). `deployment/docs/USER_GUIDE.md` already tells the operator to add `--health-timeout 600` for "the Whisper download". `[C]` |
| F14 | The `deployment` repository has uncommitted changes that are not part of this plan (`config/catalogue.toml`, `config/layouts/stepper-on-pi.toml`, camera files, `docs/DEPLOYMENT.md`, `docs/USER_GUIDE.md`; seen 2026-11-06). Another service's plan may edit `docker/service.Dockerfile` and `docker_runtime.py` too: read `git status` and `git diff` of a file before editing it. `[C]` |
| F15 | The new settings and the fetch step are environment variables and files of this service: **no `contracts` change** is needed. `[C]` |
| F16 | Portability, `pip install --dry-run --only-binary=:all:` of the runtime packages (fastapi, uvicorn, python-dotenv, pydantic, numpy, openai, faster-whisper, httpx): resolves for CPython 3.12 on `manylinux_2_28_aarch64` and on `manylinux_2_28_x86_64`, and for CPython 3.11 on `manylinux_2_28_aarch64`. Nothing was installed or run on aarch64. `[D]` |
| F17 | Docker Desktop 29.5.2 is running here (`desktop-linux`, linux/x86_64, the active context); the contexts `default` and `raspberry` (`ssh://pi@...`) also exist. No image was built. `[D]` |
| F18 | Existing tools for the checks: `contracts/tests/e2e/make_speech.py "<text>" <out.wav>` (run with the tts venv; SAPI on Windows) makes a spoken WAV; `contracts/tests/e2e/test_real_pipeline.py` runs the real stt (`STT_ENGINE=local`) behind Brain but only with `E2E_REAL_LLM=1` and real provider keys; `stt_microservice/tests/simple.py` needs a running service and real audio. `[C]` |
| F19 | The service documents already list this work as planned: FR-8, NFR-9, NFR-10, NFR-11 in [../requirements/requirements.md](../requirements/requirements.md), debts 1 to 3 and 7 in [../architecture/architecture.md](../architecture/architecture.md) (section 8), and the *Known limitations* of [../../README.md](../../README.md). The ADR index ends at ADR-007, so the next numbers are ADR-008 and ADR-009. `[C]` |

## 5. Status board

| ID | Task | Kind | Status |
|---|---|---|---|
| [T-01](T-01_deployment-readiness/T-01_deployment-readiness.md) | **Deployment readiness of the service** (epic) | epic | in-progress |
| [T-01.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1_baseline-checks.md) | Baseline checks (no code change) | group | in-progress |
| [T-01.1.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.1_clean-clone-install-and-tests.md) | Clean clone: install and tests | test | done |
| [T-01.1.2](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.2_native-deploy-local-engine.md) | Native deploy with the tool: local engine and gate | manual | done |
| [T-01.1.3](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.3_real-transcription.md) | Real transcription on the deployed service | manual | done |
| [T-01.1.4](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.4_openai-engine.md) | OpenAI engine on the deployed service | manual | done |
| [T-01.1.5](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.5_failure-drills.md) | Failure drills | manual | done |
| [T-01.1.6](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.6_pipeline-with-fake-hardware.md) | Pipeline tests with fake hardware | test | done |
| [T-01.1.7](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.7_wake-phrase-round-trip.md) | Wake-phrase round trip through Brain | manual | done |
| [T-01.2](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2_local-model-settings.md) | Local model settings | group | done |
| [T-01.2.1](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.1_settings-decision.md) | Decision: the shape of the local-model settings | decision | done |
| [T-01.2.2](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.2_config-fields.md) | `SttConfig`: model, threads, compute type | code | done |
| [T-01.2.3](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.3_engines-use-settings.md) | The engines use the settings | code | done |
| [T-01.3](T-01_deployment-readiness/T-01.3_model-download-step/T-01.3_model-download-step.md) | Model download step | group | done |
| [T-01.3.1](T-01_deployment-readiness/T-01.3_model-download-step/T-01.3.1_pin-fetch-script.md) | Pin the behaviour of the fetch script with tests | test | done |
| [T-01.3.2](T-01_deployment-readiness/T-01.3_model-download-step/T-01.3.2_fetch-main-model.md) | Fetch the main model too | code | done |
| [T-01.4](T-01_deployment-readiness/T-01.4_requirements-split.md) | Split the runtime and dev requirements | code | done |
| [T-01.5](T-01_deployment-readiness/T-01.5_service-documents.md) | Service documents true again | docs | done |
| [T-01.6](T-01_deployment-readiness/T-01.6_pin-runtime-dependencies.md) | Pin the runtime dependencies | code | done |
| [T-01.7](T-01_deployment-readiness/T-01.7_hide-openai-error-text.md) | Do not echo part of a wrong OpenAI key | code | done |
| [T-02](T-02_deployment-tool-changes/T-02_deployment-tool-changes.md) | **Deployment tool changes** (the `deployment` repository) | epic | done |
| [T-02.1](T-02_deployment-tool-changes/T-02.1_model-delivery-decision.md) | Decision: how the models reach a container | decision | done |
| [T-02.2](T-02_deployment-tool-changes/T-02.2_named-volumes.md) | Named volumes for a service | code | done |
| [T-02.3](T-02_deployment-tool-changes/T-02.3_prepare-in-the-container.md) | Run the `prepare` step against the real settings in Docker | code | done |
| [T-02.4](T-02_deployment-tool-changes/T-02.4_stt-catalogue-entry.md) | The stt catalogue entry: volume and `HF_HOME` | code | done |
| [T-02.5](T-02_deployment-tool-changes/T-02.5_inventory-and-manual.md) | Inventory and manual: the new settings | docs | done |
| [T-03](T-03_docker-and-arm64-acceptance/T-03_docker-and-arm64-acceptance.md) | **Docker and arm64 acceptance** | epic | in-progress |
| [T-03.1](T-03_docker-and-arm64-acceptance/T-03.1_amd64-build.md) | Build the image on amd64 | manual | done |
| [T-03.2](T-03_docker-and-arm64-acceptance/T-03.2_run-and-call.md) | Run the container and call it | manual | done |
| [T-03.3](T-03_docker-and-arm64-acceptance/T-03.3_restart-without-redownload.md) | Restart and recreate without a re-download | manual | done |
| [T-03.4](T-03_docker-and-arm64-acceptance/T-03.4_image-contents-and-secrets.md) | Image contents and secrets | manual | done |
| [T-03.5](T-03_docker-and-arm64-acceptance/T-03.5_first-start-without-network.md) | First start without network | manual | done |
| [T-03.6](T-03_docker-and-arm64-acceptance/T-03.6_native-on-a-raspberry-pi.md) | Native on a Raspberry Pi: install and speed | manual | postponed |
| [T-03.7](T-03_docker-and-arm64-acceptance/T-03.7_docker-on-arm64.md) | Docker on arm64 | manual | postponed |
| [T-03.8](T-03_docker-and-arm64-acceptance/T-03.8_record-the-results.md) | Record what was verified | docs | in-progress |
| [T-04](T-04_documentation-sync.md) | **Documentation sync** (recurring) | docs | recurring |
