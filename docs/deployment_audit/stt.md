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
