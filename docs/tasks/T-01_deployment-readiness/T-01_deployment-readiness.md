# T-01 — Deployment readiness of the service

| | |
|---|---|
| Status | in-progress |
| Kind | epic |
| Depends on | — |
| Blocks | T-03 |

## Goal

A deploy of `stt_microservice` (native on Windows, native on Linux or a Raspberry Pi, and Docker) that comes up with the engine the settings ask for, has its local models ready **before** Brain's 60 s preflight, runs only what it needs at run time, and can be tuned for a small CPU without editing code. Today the local model, its compute type and its thread count are constants (debt 1, FR-8), the `prepare` step downloads only the gate's model (debt 3, NFR-9), and the pytest/ruff/black/mypy tools are installed in every deploy (debt 2, NFR-10).

## Why

The deployment audit ([../../deployment_audit/stt.md](../../deployment_audit/stt.md)) found a service that is sound in code and has three deployment gaps. The tasks first measure what a fresh deploy really does today with no code change (T-01.1), then make the local model configurable (T-01.2), make the `prepare` step fetch what the settings need (T-01.3), and take the dev tools out of the runtime install (T-01.4). T-01.5 makes the documents true again. The Docker half of the audit (a model cache that survives a recreated container) cannot be done in this repository alone: it is T-02, in the `deployment` repository.

## Decisions kept (do not reopen)

- **Brain is the only coordinator** and the service makes no outgoing calls except to the OpenAI API (ADR-006, NFR-2). Nothing in this plan adds a service-to-service call.
- **The defaults do not change behaviour:** with no new setting in the `.env`, the service loads `small.en`, `int8`, 2 threads, exactly as today.
- **Secrets stay out of images and documents:** the `.env` is bind-mounted read-only at run time and excluded from the build context; the plan keeps it that way (F8).
- **No `contracts` change** (F15).

## Subtasks

| Order | Task | State |
|---|---|---|
| 1 | [T-01.1 Baseline checks](T-01.1_baseline-checks/T-01.1_baseline-checks.md) | in progress (T-01.1.1 to T-01.1.6 done) |
| 2 | [T-01.2 Local model settings](T-01.2_local-model-settings/T-01.2_local-model-settings.md) | done |
| 3 | [T-01.3 Model download step](T-01.3_model-download-step/T-01.3_model-download-step.md) | done |
| 4 | [T-01.4 Split the runtime and dev requirements](T-01.4_requirements-split.md) | done |
| 5 | [T-01.5 Service documents true again](T-01.5_service-documents.md) | done |
| 6 | [T-01.6 Pin the runtime dependencies](T-01.6_pin-runtime-dependencies.md) | done |
| 7 | [T-01.7 Do not echo part of a wrong OpenAI key](T-01.7_hide-openai-error-text.md) | done |

## Exit criteria

- T-01.1 is done and its findings are in the *Notes* of its leaves (what the local engine, the gate and the OpenAI engine really do on a deploy; how long a first start takes).
- `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE` exist, default to today's values, reach the main model and the gate, and are covered by tests.
- The `prepare` step downloads every local model the settings make the service load, and its exit codes are pinned by tests.
- The runtime install contains no test or lint tool.
- The documents named in [T-01.5](T-01.5_service-documents.md) say what is true.
- The runtime requirements are pinned to the versions the real engines ran with ([T-01.6](T-01.6_pin-runtime-dependencies.md)), after T-01.1.3 and T-01.1.4.
- A wrong OpenAI key is no longer echoed in part in an answer or a log ([T-01.7](T-01.7_hide-openai-error-text.md)), found by the failure drills of T-01.1.5.
