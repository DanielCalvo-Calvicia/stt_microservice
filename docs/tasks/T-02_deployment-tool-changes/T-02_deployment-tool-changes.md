# T-02 — Deployment tool changes (the `deployment` repository)

| | |
|---|---|
| Status | done |
| Kind | epic |
| Depends on | T-02.1 (a decision; each leaf names its own other dependencies) |
| Blocks | T-03 |

## Goal

Change the deployment tool so that a stt container can keep its model cache across `docker rm -f`, gets its models downloaded with the **real** settings before it starts, and so that the manual lists the new settings. Today the Docker runtime has no volume support, runs `prepare` only at build time with no `.env`, and so fetches nothing for stt (F7, F8). Nothing in the stt repository alone can fix that.

## Rules for this epic

- `deployment` is its own repository with its own `CLAUDE.md`: **read `deployment/CLAUDE.md` before editing anything** and follow it (the layered layout, "define every fact once", every external command through `Shell`, dry-run without side effects, tests for the install path, keep `docs/DEPLOYMENT.md` in step with each `.env.example`).
- The edits are made in `D:\Hobbys\IA\OBLIVION\deployment`, not in this repository. This epic lives here because its cause and its acceptance are stt's. Do not commit or push in either repository unless asked.
- The deployment tests are run with the brain venv, from `deployment/`, in the background (about 150 s): `..\brain_microservice\windows\Scripts\python.exe -m pytest tests -q`.
- The `deployment` repository already has uncommitted changes that are not part of this plan (F14), and another service's plan may edit the same Dockerfile and `docker_runtime.py`. Read `git status` and `git diff` of a file before editing it, and change only the lines the task names.
- Do not start a container or build an image in this epic: the unit tests use the fake `Shell` and `--dry-run`. Real runs are T-03.

## Subtasks

| Order | Task | Kind | State |
|---|---|---|---|
| 1 | [T-02.1 Decision: how the models reach a container](T-02.1_model-delivery-decision.md) | decision | done |
| 2 | [T-02.2 Named volumes for a service](T-02.2_named-volumes.md) | code | done |
| 3 | [T-02.3 Run the `prepare` step against the real settings in Docker](T-02.3_prepare-in-the-container.md) | code | done |
| 4 | [T-02.4 The stt catalogue entry: volume and `HF_HOME`](T-02.4_stt-catalogue-entry.md) | code | done |
| 5 | [T-02.5 Inventory and manual: the new settings](T-02.5_inventory-and-manual.md) | docs | done |

## Exit criteria

A `docker run` line for stt carries a named volume and the generated `.env`; the generated `.env` of a Docker stt sets `HF_HOME` inside that volume; a deploy, update and rollback of a Docker stt run the `prepare` script against the real settings before the container starts; every other service's commands are unchanged; `deployment/docs/DEPLOYMENT.md` and the stt manual of this repository say the same; the deployment suite passes.
