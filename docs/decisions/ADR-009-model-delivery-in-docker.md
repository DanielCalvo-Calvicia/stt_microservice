# ADR-009: In Docker the local models live in a named volume and the `prepare` step runs against the real settings

- **Status:** Accepted, not built (the deploy-tool changes are T-02.2 to T-02.5 in `docs/tasks`).
- **Date:** 2026-11-06.

## Context

The deploy tool recreates the container on every start (`docker rm -f`, then `docker run`) and mounts only the generated `.env`, read-only; it has no volume support. A local model (the main one when `STT_ENGINE` is not `openai`, and the wake-phrase gate's) downloads into the Hugging Face cache, so a recreated container downloads it again, and a first start without network fails. The `prepare` step (`scripts/fetch_gate_model.py`) runs in the Dockerfile at image build time, when no `.env` exists, so it sees the defaults (OpenAI engine, gate off) and fetches nothing. The default engine, OpenAI, needs no model; the problem matters only for the local engine and the gate. Options considered: a volume with a download at the first start (A), a volume plus a run-time `prepare` (B), models baked into the image (C), no change (D).

## Decision

Option B ([T-02.1](../tasks/T-02_deployment-tool-changes/T-02.1_model-delivery-decision.md), answers of [Q01](../questionnaires/Q01_before-the-deployment-tasks.md)):

- The tool mounts a named volume `oblivion-stt-models` at `/models` and sets `HF_HOME=/models/huggingface` **only for Docker**; a native install keeps the default cache.
- After the build and before the service starts (deploy, update, rollback), the tool runs stt's `prepare` script once in a throw-away container that has the volume and the real `.env`, as the native path does. Which services use the run-time step is chosen per service by a catalogue key; stt asks for it.
- A download that fails at deploy is a warning and the deploy continues; the service then fails its own start with a clear error.
- `stop` and `rm` never delete the volume; the operator removes it with `docker volume rm oblivion-stt-models`.

## Consequences

- A normal deploy never starts stt with an empty cache while the network is up, so the deploy's 60 s health wait and Brain's 60 s preflight are not at risk; the image stays free of models and secrets.
- The change is in the `deployment` repository (another repo), plus `scripts/fetch_gate_model.py` fetching the main model too (built in T-01.3.2, 2026-11-08).
- A first start with an empty volume and no network still fails; that is documented and tested in T-03.5.
- Not yet verified: the first-start time with a local model (T-01.1.2), the restart without a re-download (T-03.3). This record gets a dated note with the measured time.

> **Update 2026-11-06 (T-01.1.2):** the first start of a **native** install with an empty cache, on the maintainer's Windows PC with a fast connection, took about 28 s to download and load the main model `small.en` (464 MB) after `prepare` had fetched the gate's `tiny.en` (75 MB), and the whole `deploy` took 126 s. That is under the 60 s waits of the deploy tool and of Brain's preflight; it says nothing yet about a Raspberry Pi (T-03.6) or a container (T-03.2, T-03.3). A warm restart took 5 s. This note does not change the decision.

> **Update 2026-11-09 (T-02.2 to T-02.5):** built in the `deployment` repository as decided: catalogue keys `volumes`, `prepare_at_run` and `docker_env` (a Docker-only variable in the computed layer), the stt entry with `volumes = { models = "/models" }` and `HF_HOME=/models/huggingface`, the build without the `PREPARE` argument for a `prepare_at_run` service, and `docker run --rm` of the prepare command between the build and the start. Tested with fake shells (`deployment/tests/test_docker_volumes.py`); the restart without a re-download and the no-network first start are still unproven until T-03.3 and T-03.5 run with a real image.
