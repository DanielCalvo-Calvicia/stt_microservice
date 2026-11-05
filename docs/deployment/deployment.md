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

Local models are downloaded the first time they load. To fetch the gate model before the first start (what `prepare` does):

```powershell
& windows\Scripts\python.exe scripts\fetch_gate_model.py
```

It reads the same settings as the service, prints `STT_GATE_ENABLED is off: no gate model needed` and exits `0` when the gate is off, and otherwise loads `STT_GATE_MODEL` (CPU, int8) and exits `1` if it cannot. **It does not fetch the main local model** (`small.en`, used when `STT_ENGINE` is not `openai`): that one downloads when the service first starts.

## Tools and versions

| Item | Value |
|---|---|
| Python | 3.14 in the workspace venv `windows\Scripts\python.exe`; 3.12 in the deploy Docker image (`deployment/docker/service.Dockerfile`); `pyproject.toml` targets 3.11 |
| Runtime packages | fastapi, uvicorn, python-dotenv, pydantic, numpy, openai, faster-whisper, httpx; `-e ../shared-logging`; the contracts 0.15.0 wheel in `vendor/` |
| Also installed today (debt) | pytest, ruff, black, mypy: they are in both requirement files, so the Docker build installs them (`filtered_requirements` only drops the `-e ../` lines) |
| Contracts | refreshed with `contracts/scripts/bundle.py`; the wheel makes the service build on its own |

## Docker (through the deploy tool)

Feasible, with these issues (all read in `deployment/`, none run here):

- **The model cache does not persist.** A local model downloads into the Hugging Face cache at first use. `docker_runtime.start` does `docker rm -f` and mounts only the `.env`, so a recreated container downloads again, and a first start without network fails (the engine loads its model in its constructor, so `--restart unless-stopped` then loops).
- **`prepare` fetches nothing in a container.** The Dockerfile runs it at *build* time, when no `.env` exists, so the settings have their defaults (openai, gate off) and the script returns early. Even the gate model is never baked in.
- **Secrets are handled correctly:** `.env` is excluded from the build context and bind-mounted read-only at run time, never an image layer.

What would fix it is in `deployment/` (another repo): a named volume with `HF_HOME` pointing into it, and downloading the models at run time. Nothing in this repository alone makes the cache survive a recreated container. **Planned, not done.**

## Portability

Pure Python plus compiled wheels. A `pip install --dry-run` for CPython 3.12 on `manylinux_2_28_aarch64` resolved faster-whisper, ctranslate2, onnxruntime, av, tokenizers and numpy as binary wheels (2026-11-04). With only the older `manylinux2014_aarch64` tag onnxruntime does not resolve; the Docker base (Debian bookworm) satisfies the newer tag. **Not verified:** an install and a run on real aarch64 or a Raspberry Pi; the speed of a local model on a Pi; amd64 and arm64 containers.

## Rollback

Not documented by this repository. The deploy tool's `rollback` re-runs the `prepare` step; a previous version of the service is the previous commit of this repo.

## Not yet verified

A real OpenAI call, a real faster-whisper run, `tests/simple.py`, a Docker restart without a re-download, `docker history` / `docker inspect` showing no key, the service on a Raspberry Pi.
