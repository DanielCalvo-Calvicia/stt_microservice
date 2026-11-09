# Deployment

How the service is delivered. **This repository has no Dockerfile, no CI and no manifests.** The service is installed and started by the workspace's `deployment/` tool (its own repo, a stdlib CLI), which reads this service's entry in `deployment/config/catalogue.toml`. The audit of 2026-11-04 ([deployment_audit/stt.md](../deployment_audit/stt.md)) checked the Docker path; its findings are summarised here. Nothing here was run on real Linux or Raspberry Pi hardware.

## What the deploy tool knows about this service

| Item | Value | Source |
|---|---|---|
| Repository and branch | `stt_microservice`, `feature_ai_claude_2` | `catalogue.toml` |
| Port | `8001` (`SERVICE_PORT`) | `catalogue.toml` |
| Readiness probe | `GET /available` | `catalogue.toml` (`ready`) |
| Requirements | `requirements.windows.txt` / `requirements.linux.txt` | `catalogue.toml` |
| Library | `shared-logging` (installed with `-e ../shared-logging`) | `catalogue.toml` |
| `prepare` step | `scripts/fetch_gate_model.py`, run after the `.env` is written (deploy, update, rollback) | `catalogue.toml` |
| Default setting | `STT_ENGINE=openai`; `OPENAI_API_KEY` required when the engine is `openai` | `catalogue.toml` (`services.stt.env`, `services.stt.require`) |
| System packages | none | `catalogue.toml` |
| Who calls it | Brain, through `STT_BASE_URL` and the routes `STT_SET_STREAM`, `STT_GET_STREAM`, `STT_BATCH` | `deployment/docs/DEPLOYMENT.md` |

Start order: STT does not depend on any other service; Brain starts last and waits for it (`STARTUP_PREFLIGHT_*` on Brain). The wake-phrase gate needs `STT_GATE_ENABLED=1` here **and** `WAKE_PHRASE_ENABLED=1` on Brain.

## Run by hand

```powershell
& windows\Scripts\python.exe main.py
curl http://127.0.0.1:8001/available
```

Local models are downloaded the first time they load. To fetch the models before the first start (what `prepare` does):

```powershell
& windows\Scripts\python.exe scripts\fetch_gate_model.py
```

It reads the same settings as the service (the environment, then the `.env` next to `main.py`) and loads, once each, with the service's own `STT_THREADS` and `STT_COMPUTE_TYPE`: the **main model** (`STT_MODEL`) when `STT_ENGINE` is not `openai`, then the **gate's model** (`STT_GATE_MODEL`) when `STT_GATE_ENABLED` is on; a name needed twice is loaded once. With the OpenAI engine and the gate off it prints `No local model needed: STT_ENGINE is openai and STT_GATE_ENABLED is off` and exits `0`. A model that cannot be loaded prints `Could not load the main model <name>: <reason>` (or `gate`) on stderr and does not stop the other one; the exit code is `1` if any failed, `0` otherwise. A bad `STT_THREADS` prints `Invalid settings: ...` and exits `1`. Since T-01.3.2 (2026-11-08); run for real on a Windows PC with a throw-away cache: the main model `small.en` (464 MB) took 52 s cold and 3 s warm, and with the gate on `tiny.en` (75 MB) was added in 12 s.

## Tools and versions

| Item | Value |
|---|---|
| Python | 3.14 in the workspace venv `windows\Scripts\python.exe`; 3.12 in the deploy Docker image (`deployment/docker/service.Dockerfile`); `pyproject.toml` targets 3.11 |
| Runtime packages | fastapi 0.162.0, uvicorn 0.54.0, python-dotenv 1.2.4, pydantic 2.14.3, numpy 2.5.4, openai 3.46.0, faster-whisper 1.2.1, **pinned exactly** since T-01.6 (2026-11-08): the versions installed where the engines ran for real on 2026-11-06 (Python 3.14). Their own dependencies are not pinned (no lock file). The `numpy` pin applies from Python 3.12; on 3.11 the line falls back to `numpy>=1.26.4` (not proven). To move a pin: install it, run the engines, change the line; `-e ../shared-logging`; the contracts 0.15.0 wheel in `vendor/` (the committed version; the working tree has the maintainer's uncommitted 0.16.0) |
| Dev tools | pytest, httpx, ruff, black, mypy are in `requirements.dev.txt` since T-01.4 (2026-11-08). The deploy tool reads only the two files the catalogue names (`requirements.windows.txt`, `requirements.linux.txt`), so neither a native deploy nor the Docker build installs them. A venv built before keeps them until it is rebuilt. Checked with a clean runtime-only venv (no pytest, ruff, black or mypy; the service answered `/health` and `/available`) and a venv with both files (140 tests passed) |
| Contracts | refreshed with `contracts/scripts/bundle.py`; the wheel makes the service build on its own |

## Docker (through the deploy tool)

Feasible. The audit (2026-11-04) read the issues below in `deployment/`; the first two were fixed and are verified on amd64 with Docker Desktop on 2026-11-09 (T-03.1 to T-03.5): an image of 865 MB built on Python 3.12.16 without compiling anything, the run-time `prepare` filled the volume `oblivion-stt-models` (539 MB), the container transcribed with the local engine and the gate, and a restart (3.1 s), a recreate (5.4 s) and a rebuild did not download again.

- **(Fixed 2026-11-09) The model cache did not persist.** A local model downloads into the Hugging Face cache at first use. `docker_runtime.start` does `docker rm -f` and mounts only the `.env`, so a recreated container downloads again, and a first start without network fails (the engine loads its model in its constructor, so `--restart unless-stopped` then loops).
- **(Fixed 2026-11-09) `prepare` fetched nothing in a container.** The Dockerfile runs it at *build* time, when no `.env` exists, so the settings have their defaults (openai, gate off) and the script returns early. Even the gate model is never baked in.
- **Secrets are handled correctly:** `.env` is excluded from the build context and bind-mounted read-only at run time, never an image layer.

What would fix it is in `deployment/` (another repo): a named volume with `HF_HOME` pointing into it, and downloading the models at run time. Nothing in this repository alone makes the cache survive a recreated container. **Built and verified 2026-11-09, see the updates below.**

> **Update 2026-11-06:** decided (option B, [ADR-009](../decisions/ADR-009-model-delivery-in-docker.md)): the named volume `oblivion-stt-models` at `/models` with `HF_HOME=/models/huggingface` set only for Docker, and stt's `prepare` run once in a throw-away container with the volume and the real `.env` before the service starts; a failed download is a warning; the volume is never deleted automatically. Still **not built** (tasks T-02.2 to T-02.5 in [../tasks](../tasks/README.md)) and not run.

> **Update 2026-11-09 (T-02.2 to T-02.5):** built in the `deployment` repository. The catalogue's stt entry now has `volumes = { models = "/models" }`, `prepare_at_run = true`, `internal = ["HF_HOME"]` and `[services.stt.docker_env] HF_HOME = "/models/huggingface"`. The image build no longer runs `prepare` for stt; `deploy`, `update` and rollback run `docker run --rm` of the built image with the written `.env` and the volume before the service container starts (a failure is the usual `warning: stt: ... failed` line); the service's own `docker run` mounts the volume too, and the generated `.env` of a Docker stt carries `HF_HOME` (a native one does not). Covered by `deployment/tests/test_docker_volumes.py` with fake shells (11 of 11 one-line mutations caught). **No image was built and no container run**: the two bullets above ("the cache does not persist", "`prepare` fetches nothing in a container") describe the audit and are expected to be false now; T-03.1 to T-03.5 prove it. The Raspberry Pi parts (T-03.6, T-03.7) are postponed until the service works fully on Windows.

## What a failed start looks like

Checked on 2026-11-06 on a Windows PC with a scratch deployment (T-01.1.5); each case is a native deploy with the tool. In every case the service exits with code 1 and **the reason is only in its log** (`oblivion.py logs -s stt`); the deploy tool prints "health: no answer" and waits the **whole** health timeout (62 s by default) even though the service died within seconds.

| Cause | `validate` and `deploy` | The service |
|---|---|---|
| `STT_ENGINE=openai` and no `OPENAI_API_KEY` | refused before anything starts: `OPENAI_API_KEY is required when STT_ENGINE=openai` (exit 1, 1 s) | if started by hand: exit 1 with a traceback ending in `EngineNotConfigured` |
| A local model that is not in the cache and cannot be downloaded (empty `HF_HOME`, `HF_HUB_OFFLINE=1`) | `prepare` does nothing with the gate off; `deploy` ends `FAILED ... health: no answer` after 62 s | `LocalEntryNotFoundError: Cannot find an appropriate cached snapshot folder ...`, exit 1 |
| A mistyped `STT_GATE_MODEL` (gate on) | `prepare` warns with the list of valid names and the deploy goes on, then `FAILED` after 63 s | `ValueError: Invalid model size '<name>', expected one of: ...`, exit 1 |
| A bad `STT_THREADS` | not checked by `validate` | `ValueError: STT_THREADS must be a whole number >= 0 ...`, exit 1 (the `prepare` script says `Invalid settings: ...`) |
| A wrong OpenAI key | the service starts and `/available` is true (it never calls the API) | the first utterance is a `500` with the fixed message `OpenAI request failed: AuthenticationError (HTTP 401)` |

**A slow first start.** With an empty cache the service downloads its model before it listens: 28 to 38 s for `small.en` on a PC with a fast connection, under the 60 s of the deploy wait and of Brain's preflight. When a first start outlives the wait (simulated with `--health-timeout 10`), `deploy` exits 1 and `status` says `UNHEALTHY` while the service is still downloading, and `status` says `healthy and available` once it has finished. A first start on a Raspberry Pi has not been measured. `restart: unless-stopped` is not in play natively, so no crash loop was seen; in Docker it is not run.

## Portability

Pure Python plus compiled wheels. A `pip install --dry-run` for CPython 3.12 on `manylinux_2_28_aarch64` resolved faster-whisper, ctranslate2, onnxruntime, av, tokenizers and numpy as binary wheels (2026-11-04). With only the older `manylinux2014_aarch64` tag onnxruntime does not resolve; the Docker base (Debian bookworm) satisfies the newer tag. **Not verified:** an install and a run on real aarch64 or a Raspberry Pi; the speed of a local model on a Pi; amd64 and arm64 containers.

Checked in T-01.6 (2026-11-08): `pip install --dry-run --only-binary=:all:` of the pinned files resolves only binary wheels for CPython 3.11 (with the numpy fallback), 3.12 and 3.13 on `aarch64` and CPython 3.11 and 3.12 on `x86_64` (all with the `manylinux_2_28`, `manylinux_2_17` and `manylinux2014` tags), and for 3.12, 3.13 and 3.14 on Windows. Two clean venvs on Windows (Python 3.14.2), one from each requirements file, installed exactly the pinned versions, the service started and answered `/health` and `/available`, and the suite passed (140). The unpinned packages resolved on 2026-11-08 to the same versions as in the venv where the engines ran, except `contracts` (0.15.0 there, 0.16.0 in the working tree). The pins were **not** run natively on Linux or a Raspberry Pi.

## Rollback

Not documented by this repository. The deploy tool's `rollback` re-runs the `prepare` step; a previous version of the service is the previous commit of this repo.

## Verified deployments

| Date | Machine | Architecture, Python | Runtime | Engine | What was checked |
|---|---|---|---|---|---|
| 2026-11-06 | Windows PC (i7-14700K) | amd64, Python 3.14 | native, with the deploy tool | local `small.en` + gate `tiny.en`; OpenAI | deploy 126 s, real transcription, failure drills, `tests/simple.py` (T-01.1) |
| 2026-11-09 | the same PC, Docker Desktop 29.5.2 | amd64, Python 3.12.16 in the image | Docker, with the deploy tool (source: a copy of the working tree) | local `small.en` + gate `tiny.en`; OpenAI | build without compiling and without dev tools or secrets, run-time `prepare` into the volume, transcription and gate through the container, restart, recreate and rebuild without a download, OpenAI engine in the container (exact text in 1.89 s, no key in the log, `inspect` or the history), load from the volume with the network off, first start with an empty volume and no network (crash loop) and with a filled one (T-03.1 to T-03.5) |

## Not yet verified

A reliable wake-phrase recognition (the round trip through Brain with a real microphone ran on 2026-11-09 and works, but the gate heard the name 1 time in 4: see the table), and a Raspberry Pi, native or in Docker on arm64 (T-03.6, T-03.7: **postponed by the maintainer on 2026-11-09** until the services work fully on Windows). Also not checked: a deploy from the pushed branch (the Docker run used a copy of the unpushed working tree), and a Linux host.

> **Update 2026-11-06 (T-01.1.2):** a native deploy with the deploy tool, `STT_ENGINE=local` and the gate on, on the maintainer's Windows PC with an empty Hugging Face cache, ran to `healthy and available` in 126 s. The `prepare` step fetched only the gate model `tiny.en` (75 MB); the first start downloaded and loaded the main model `small.en` (464 MB) in about 28 s; a warm restart took 5 s. No audio was transcribed in that run (T-01.1.3). Details in [the task](../tasks/T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.2_native-deploy-local-engine.md) and [ADR-009](../decisions/ADR-009-model-delivery-in-docker.md).

> **Update 2026-11-06 (T-01.1.3):** on the same scratch deployment the local engine transcribed spoken English for real (`small.en`, about 4.5 to 5 s per utterance on an Intel Core i7-14700K with 2 threads; the cost is nearly the same for a 2 s and a 4 s utterance) and the gate (`tiny.en`) returned the wake phrase with the utterance audio in under 1 s; `tests/simple.py` ran (its two checks pass with `python -X utf8`). The speed on a Raspberry Pi is still unknown (T-03.6).

> **Update 2026-11-06 (T-01.1.4):** the default engine ran for real on the same scratch deployment: `STT_ENGINE=openai` with the maintainer's key (supplied to the scratch settings by a script, never printed), the gate off, deployed in 4 s (`prepare` printed `STT_GATE_ENABLED is off: no gate model needed`). `/available` answered in 2 ms without calling the API; spoken English came back exact in about 0.7 to 1.5 s per utterance (the first call 2.7 s). The logs held the model name and lengths only. Still not run then: a Docker restart, a Raspberry Pi (the failure drills ran later: see "What a failed start looks like").

> **Update 2026-11-09 (T-03.1 to T-03.5):** the Docker run on amd64 (see the table above). Numbers: build and deploy 1 min 56 s, a second deploy (rebuild) 73 s, `docker restart` to `/available` 3.1 s, recreate with the tool 5.4 s, the volume 551,212 KiB before and after every step; `/process/batch` 2.93 s for 3.78 s of speech (the same phrase in the gate came back with `audio_base64` equal to the input). The image runs as **root** (the generic Dockerfile sets no user) and holds the whole service tree (`docs/`, `tests/`, `CLAUDE.md`), but no `.env`, no dev tools and no key (counts of `OPENAI_API_KEY` and `sk-` were 0 in `history`, `inspect` and the saved layers). With an empty volume and no network the container crash-loops (9 restarts in 45 s, `LocalEntryNotFoundError`); with the filled volume it starts offline. The settings reach the service through the mounted `.env`, so `docker exec ... printenv HF_HOME` prints nothing; read `/app/.env` instead.
