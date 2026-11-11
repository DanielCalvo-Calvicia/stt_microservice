# stt_microservice (port 8001)

Checked against the code, `deployment/` and its Dockerfile on 2026-11-04. Tags: [C] read in code or config, [D] run or dry-run here, [U] not verified.

## Role
Transcribes finished utterances (the microphone does the silence cutting). Engines: OpenAI Whisper API (default) or local faster-whisper. Optional wake-phrase "gate" (second local model) under `/gate/...`. Endpoints: `/process/stream/{set,get}`, `/process/stream`, `/process/batch`, `/health`, `/available`, `POST /stop`. [C: `CLAUDE.md`]

## Dependencies
fastapi, uvicorn, python-dotenv, pydantic, numpy, openai, faster-whisper, httpx, **pytest/ruff/black/mypy**; `-e ../shared-logging`; contracts 0.15.0 (the `CLAUDE.md` of this service still says 0.12.0). No system packages in the catalogue. [C]
The dev tools are in both `requirements.windows.txt` and `requirements.linux.txt`, and the Docker build installs them as is: `filtered_requirements` only drops `-e ../` lines. [C]

## Hardware
None (CPU).

## Portability
Pure Python plus compiled wheels. A `pip install --dry-run` for CPython 3.12 on `manylinux_2_28_aarch64` resolves faster-whisper, ctranslate2, onnxruntime, av, tokenizers and numpy as binary wheels [D]. With only the older `manylinux2014_aarch64` tag onnxruntime does not resolve; it needs the newer tag, which the Docker base (Debian bookworm) satisfies. Nothing was installed or run on real aarch64 [U].
The Docker image uses Python 3.12 (`deployment/docker/service.Dockerfile`), not 3.11. A 3.11 install of the Linux requirements file is not something I could confirm [U].

## Local
The openai and local engines are covered by the tests with fake models and clients. A real OpenAI call and a real faster-whisper run were not done in this audit [U]. Local model speed on a Pi is unknown [U].

## Docker
Feasible, with these issues:
- The Whisper model downloads into the default Hugging Face cache **at first use**. `docker_runtime.start` does `docker rm -f` and mounts only the `.env`, so nothing persists and a recreated container downloads again. [C]
- **`prepare` cannot fetch anything in a container.** The Dockerfile runs it at *build* time, when no `.env` exists (`docker_runtime.py:34` says so). `STT_ENGINE` and `STT_GATE_ENABLED` then have their defaults (openai, gate off) and `scripts/fetch_gate_model.py` returns early. So even the gate model is never baked in, and the audit's earlier idea of extending `prepare` for the main model would not change that. [C]
- The local engine loads its model in the constructor (`local_whisper_transcription.py:54`). A first start without network fails, and `--restart unless-stopped` then loops. [C]
- Needs network at first start unless the model sits in a persistent volume.
- Secrets are handled correctly: `.env` is excluded from the build context (`prepare_context`) and bind-mounted read-only at run time, never an image layer. [C]

## Configuration
`STT_ENGINE=openai` (default; cloud, needs `OPENAI_API_KEY`, secret), `STT_LANGUAGE`, `STT_PROMPT`, `STT_GATE_*`.
Not settings, hardcoded in `local_whisper_transcription.py`: device (`cpu`), compute type (`int8`), threads (`cpu_threads=2`, line 54) and the main model name (`DEFAULT_MODEL_NAME = "small.en"`, line 18; `stt_dependencies.py` passes none). The gate goes through the same class, so it has the same device, compute type and threads. [C]

## Problems
1. Hardcoded device, compute type and thread count, for both the main model and the gate.
2. The main local model name is not configurable. It is always `small.en`, which is English only, so `STT_LANGUAGE=es` with the local engine cannot work.
3. Model cache location is not controlled, and `prepare` is useless in Docker (see above): it does not fetch the main model at all, and fetches the gate model only on native installs.
4. Dev tools at runtime, including in the Docker image.
5. Cloud dependency by default. In Docker the secret handling is already right (mounted `.env`).

## Recommended changes
1. Make the main model, threads and compute type env settings (`STT_MODEL`, `STT_THREADS`, `STT_COMPUTE_TYPE`) with the current values as defaults, and use the same threads and compute type for the gate. Reject a non-numeric or negative thread count at start.
2. Put the Hugging Face cache (`HF_HOME`) on a named volume. The service reads `HF_HOME` through huggingface_hub, and `faster_whisper` is imported after `load_dotenv`, so a value in the mounted `.env` takes effect. This **needs changes in `deployment/`, a separate repo**: a `volumes` entry in the catalogue and a `--mount` in `docker_runtime.start`. Nothing in stt alone makes the cache survive a recreated container.
3. Download the models at run time into that volume (first start, or a one-off run of the prepare script with the `.env`), because build-time `prepare` has no settings. Native installs can keep using `prepare`, extended to fetch the main model when `STT_ENGINE` is not `openai`.
4. Move pytest/ruff/black/mypy to a dev requirements file.
5. After any `.env.example` change: regenerate `deployment/config/services/stt.toml` (`env_inventory.py --write`) and update the stt table in `deployment/docs/DEPLOYMENT.md`.

## Tests
- Existing suite: **90 passed** on 2026-11-04 (the 93 in `CLAUDE.md` and the README is out of date).
- New: settings tests for the new env vars; a test that the engine and the gate receive them; a test of the fetch script's model choice and exit codes (fake models, no download).
- Docker: restart the container and confirm no re-download; run on amd64 and arm64.
- Secrets: `docker history` / `docker inspect` show no key.

## Verification notes (task plan, 2026-11-06)

> **Update 2026-11-06:** while writing the task plan ([../tasks/README.md](../tasks/README.md)) each claim a task relies on was checked again in the code (`[C]`) or by running something (`[D]`). The text above is kept as the audit. Corrections and additions:
>
> - **Confirmed `[C]`:** the hardcoded `WhisperModel(...)` arguments and `DEFAULT_MODEL_NAME` (`local_whisper_transcription.py` lines 54 and 18), the main model never being passed from `stt_dependencies.py`, `fetch_gate_model.py` fetching only the gate and exiting 0 or 1, no test for that script, `prepare` running at Docker **build** time with no `.env`, no volume support and `docker rm -f` on every start in the Docker runtime, the `.env` excluded from the build context and bind-mounted read-only, the dev tools in both requirements files and in the Docker install, the image base `python:3.12-slim-bookworm`.
> - **Confirmed `[D]`:** `pytest` gives 90 passed on 2026-11-06; `HF_HOME` written in a `.env` and loaded before the engine module is imported decides the cache folder (`main_flow.http` imports neither `faster_whisper` nor `huggingface_hub` at load); with an empty cache and `HF_HUB_OFFLINE=1` the engine constructor raises `LocalEntryNotFoundError`.
> - **Correction, `httpx`:** the audit lists `httpx` among the runtime dependencies. No file of the service imports it; only the tests do (`tests/infrastructure/test_gate_http.py`). It belongs in the dev requirements; `openai` pulls it in at run time anyway.
> - **Correction, `tests/simple.py`:** the README and `CLAUDE.md` describe it as an end-to-end script that needs real audio. It only calls `GET /health` and `GET /available`, and has `127.0.0.1:8001` hard-coded.
> - **Addition, portability `[D]`:** besides CPython 3.12 on `manylinux_2_28_aarch64`, a `pip install --dry-run --only-binary=:all:` of the runtime packages also resolves for CPython 3.12 on `manylinux_2_28_x86_64` and for CPython 3.11 on `manylinux_2_28_aarch64`. This answers the "3.11 install not confirmed" remark for resolution only; nothing was installed.
> - **Addition, first-start time `[C]`:** the deploy tool waits 60 s for `/available` by default and Brain's preflight waits 60 s, while a local engine answers nothing until its model is loaded or downloaded; the user guide already advises `--health-timeout 600` for the first run. This is why a model must be in the cache before the service starts (recommended changes 2 and 3). The real time is measured in task T-01.1.2.
> - **Addition, the restart loop `[C]`:** the loop under `--restart unless-stopped` follows from the constructor failing and the container policy; it was **not run** (task T-03.5).
> - **Addition, `HF_HOME` in the deployment tool `[C]`:** a variable that is not in the service's `.env.example` draws a "typo?" warning unless the catalogue lists it in `extra_env` or `internal`; the Docker-only value would be set in the tool's computed layer, next to `SERVICE_HOST`.
> - **Not verified:** any run of a real model on aarch64 or a Raspberry Pi, the speed of `small.en` and `tiny.en` there, a built image of any architecture, `docker history` / `docker inspect` on a real image, a real OpenAI call. The plan schedules each of them.
> - **Contracts:** the audit and the documents say contracts 0.15.0; the working tree has an uncommitted edit that points the requirements files at a 0.16.0 wheel. It is not part of the plan.

## Status of the recommendations (2026-11-08, task T-01.5)

> **Update 2026-11-08:** what became of each finding. The audit text above is unchanged; the evidence is in the *Result* of each task in [../tasks](../tasks/README.md).
>
> - **Recommended change 1 (settings): done.** `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE` exist, the gate shares the threads and the compute type, and a bad `STT_THREADS` stops the start ([ADR-008](../decisions/ADR-008-local-model-settings.md); T-01.2.2, T-01.2.3; fake-model tests; a non-default value was not run with a real model). Problems 1 and 2 are closed.
> - **Recommended changes 2 and 3, native part (the fetch script): done.** `scripts/fetch_gate_model.py` fetches the main model when the engine is local and the gate's model when the gate is on, with the service's own threads and compute type (T-01.3.2; run for real: `small.en` 52 s cold, 3 s warm).
> - **Recommended changes 2 and 3, Docker part (volume, run-time download): decided, not built.** Option B of [ADR-009](../decisions/ADR-009-model-delivery-in-docker.md): the volume `oblivion-stt-models`, `HF_HOME` set only for Docker, and `prepare` run once in a throw-away container. It needs the `deployment` repository (tasks T-02.2 to T-02.5). Problem 3 stays open for Docker.
> - **Recommended change 4 (dev tools): done.** `requirements.dev.txt` (T-01.4); a runtime-only venv has none of pytest, ruff, black or mypy. Problem 4 is closed for new venvs and images.
> - **Recommended change 5 (inventory and manual): half done.** `deployment/config/services/stt.toml` was regenerated after each `.env.example` change; the stt table of `deployment/docs/DEPLOYMENT.md` was changed in one cell only (the gate prompt default). Its rows for the three new settings and the new `prepare` behaviour are task T-02.5, **not done**.
> - **Tests:** the suite is **140 passed** (the audit counted 90). The new tests cover the settings, what the engines and the gate receive, the fetch script (28 cases, 18 of 18 mutations caught) and the OpenAI error text.
> - **Found since the audit:** a wrong OpenAI key was echoed in part (first 8 and last 4 characters) in the batch answer, the stream `error` event and the log; fixed in T-01.7. The deploy tool waits the whole health timeout even when the service has already exited (a point for the `deployment` repository). With `openai` 3.x the runtime brings `httpx2`, not `httpx`.
> - **Real runs (T-01.1, a Windows PC, 2026-11-06):** a native deploy with the tool (126 s, first start 28 s for the main model), the local engine, the gate, the OpenAI engine, `tests/simple.py`, five failure drills and the workspace pipeline check (84 passed, 18 skipped). **Still not run then:** a Raspberry Pi, any Docker image (run on 2026-11-09, below), the wake-phrase round trip with a real microphone (run on 2026-11-09, below).

## Update 2026-11-09 (T-02.2 to T-02.5, and the Pi postponed)

> - **Recommended changes 2 and 3, Docker part: built, not run.** In the `deployment` repository: the volume `oblivion-stt-models`, `HF_HOME=/models/huggingface` set only for Docker, and `prepare` run once in a throw-away container before the service starts (ADR-009; tests with fake shells, 11 of 11 mutations caught). No image was built; the restart without a re-download is T-03.3. Problem 3 is closed in code for Docker and **open until it is run**.
> - **Recommended change 5: done.** The stt table of `deployment/docs/DEPLOYMENT.md` has the rows for `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE`, the cache paragraph and the Docker behaviour (T-02.5).
> - **Postponed by the maintainer:** a Raspberry Pi and Docker on arm64 (T-03.6, T-03.7) until the services work fully on Windows. The Pi remarks of the audit (aarch64 wheels, speed of the local model) stay `[D]`/`[U]` on purpose.
> - **Docker on amd64, run the same day (T-03.1 to T-03.5):** the audit's Docker findings are confirmed and now fixed: the cache did not persist and `prepare` fetched nothing at build time (the volume and the run-time `prepare` cure both: a restart, a recreate and a rebuild did not download again); a first start without network crash-loops as predicted (9 restarts in 45 s); the secret handling is as read (`.env` not in the image, mounted read-only, 0 key matches). New findings: the container runs as root, the image holds the whole service tree (`docs/`, `tests/`), and the settings reach the service through the mounted file, so `docker exec printenv` does not show them. Python 3.12.16 installed every package as a binary wheel. The OpenAI engine also ran inside the container (T-03.2 step 5), with no key in the log, `inspect` or the history. Problem 3 is closed for Docker on amd64.
> - **Wake-phrase round trip with a real microphone, run the same day (T-01.1.7):** the flow works through Brain (no phrase: no batch request; phrase: exactly one request with the gate's own audio). The gate's recognition of the name was weak (`tiny.en` 0 of 1, `base.en` 1 of 3), and Brain logs the text of ignored utterances (`gate_heard`).
> - **Gate tuned the same day (offline, 16 real clips):** the defaults became `STT_GATE_MODEL=base` and `STT_GATE_PROMPT=Oblivion 306.` (see ADR-005). The audit's Pi remarks about the gate's `tiny.en` now describe the old default.
> - **Gate re-test live (same day):** with the new defaults only 2 of 8 phrases were accepted although offline 8 of 10 were; the cause is open (the microphone cutter's start, the trailing silence, or the speaker). See ADR-005.
> - **Gate re-test, diagnosis (same day):** the live gap came from the microphone service's cutter, which starts utterances 0.01 to 0.12 s late (smoothed volume, no pre-roll); with the clip starting 0.1 s before the voiced onset the same gate accepts 9 or 10 of 10. Details and the candidate fixes (smoothing off, or a pre-roll in the microphone) are in ADR-005.
> - **Third live test (same day, both fixes):** every phrase that reached the gate was accepted (4 of 4); 6 of 11 utterances were dropped by Brain's echo guard while the robot was speaking. See ADR-005.
