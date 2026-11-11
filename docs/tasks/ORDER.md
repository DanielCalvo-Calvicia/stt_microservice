# Task order

The order in which the tasks must be done, with the state of each one and the date its file was last updated. It follows the execution protocol of the [tasks README](README.md) (section 2): the first task that is `todo` and whose dependencies are `done`. Dependencies are in each task file; decisions that stop the chain are marked.

**Keep this file true:** every change to a task (a status, a dependency, a new task, an order change) updates this table, the board of the [tasks README](README.md) section 5 and the task file itself (see `CLAUDE.md` at the root of the repository). The *Last updated* column is the date of the last change to the task file and is refreshed by the same change.

## States

| State | Meaning |
|---|---|
| Done | Implemented and verified (or, for a decision, taken and recorded) |
| In progress | Some of its sub-tasks are done and some are not |
| Todo | Ready to start when its dependencies are done |
| Awaiting user | A decision needs the maintainer's answer; it stops the tasks that depend on it (none today) |
| Blocked | Waits, directly or through other tasks, for a decision (none today) |
| Recurring | Repeated after every big task |

Written on 2026-11-06 from the deployment audit. The decision T-01.2.1 was taken the same day (option A). Done so far: T-01.1.1 to T-01.1.6 (checks, no code change), the tests T-01.3.1 (the fetch script) and the code tasks T-01.3.2 (it fetches the main model too), T-01.4 (the requirements split), the documents task T-01.5, T-01.6 (pins), T-01.7 (the OpenAI engine's fixed failure message) T-01.2.2 and T-01.2.3 (the three local-model settings are read into `SttConfig` and used by the main model and the gate). **Todo (next)** is the task to start now: T-01.1.7 (T-01.1.1 to T-01.1.6 are done; it needs the real microphone, so T-01.2.2 or T-01.7 can go first). No decision is open any more: T-02.1 was decided on 2026-11-06 (option B, ADR-009) and nothing is blocked; every task waits only on its dependencies.

## A. Deployment readiness of the service (T-01)

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 1 | [T-01](T-01_deployment-readiness/T-01_deployment-readiness.md) | Deployment readiness of the service | epic | In progress | T-01.2.1 decided | — | 2026-11-06 |
| 2 | [T-01.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1_baseline-checks.md) | Baseline checks | group | In progress | T-01.1.1 to T-01.1.6 done; no code change | — | 2026-11-06 |
| 3 | [T-01.1.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.1_clean-clone-install-and-tests.md) | Clean clone: install and tests | test | Done | 90 passed in a clean clone; lone-clone install fails as F3 says | — | 2026-11-06 |
| 4 | [T-01.1.2](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.2_native-deploy-local-engine.md) | Native deploy with the tool: local engine and gate | manual | Done | cold first start 28 s, warm 5 s; prepare fetched the gate model only | T-01.1.1 | 2026-11-06 |
| 5 | [T-01.1.3](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.3_real-transcription.md) | Real transcription on the deployed service | manual | Done | small.en 4.5 to 5 s per utterance, tiny.en 0.7 s; text exact | T-01.1.2 | 2026-11-06 |
| 6 | [T-01.1.4](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.4_openai-engine.md) | OpenAI engine on the deployed service | manual | Done | exact text, 0.7 to 1.5 s per utterance; no key or text in the logs | T-01.1.2 | 2026-11-06 |
| 7 | [T-01.1.5](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.5_failure-drills.md) | Failure drills | manual | Done | missing key refused by the tool; offline or a typo only visible in the log; a wrong key is echoed in part | T-01.1.2 | 2026-11-06 |
| 8 | [T-01.1.6](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.6_pipeline-with-fake-hardware.md) | Pipeline tests with fake hardware | test | Done | 84 passed, 18 skipped (10 real-LLM, 8 missing requirement files) | T-01.1.1 | 2026-11-06 |
| 9 | [T-01.1.7](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.7_wake-phrase-round-trip.md) | Wake-phrase round trip through Brain | manual | Done | run 2026-11-09 with the real microphone; the path works, the gate heard the name 1 time in 4 (see the task) | T-01.1.3 | 2026-11-09 |
| 10 | [T-01.2](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2_local-model-settings.md) | Local model settings | group | Done | the three settings are read and used by the main model and the gate | — | 2026-11-06 |
| 11 | [T-01.2.1](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.1_settings-decision.md) | Decision: the shape of the local-model settings | decision | Done | option A chosen 2026-11-06 | — | 2026-11-06 |
| 12 | [T-01.2.2](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.2_config-fields.md) | `SttConfig`: model, threads, compute type | code | Done | read into SttConfig, ADR-008 written; engines wired in T-01.2.3 | T-01.2.1, T-01.1.1 | 2026-11-06 |
| 13 | [T-01.2.3](T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.3_engines-use-settings.md) | The engines use the settings | code | Done | 112 passed; fake-model tests; gate prompt default set to Oblivion | T-01.2.2 | 2026-11-06 |
| 14 | [T-01.3](T-01_deployment-readiness/T-01.3_model-download-step/T-01.3_model-download-step.md) | Model download step | group | Done | the script fetches the main model and the gate model | — | 2026-11-06 |
| 15 | [T-01.3.1](T-01_deployment-readiness/T-01.3_model-download-step/T-01.3.1_pin-fetch-script.md) | Pin the behaviour of the fetch script with tests | test | Done | 17 test cases, 9 of 9 mutations caught; the script is unchanged | T-01.1.1 | 2026-11-06 |
| 16 | [T-01.3.2](T-01_deployment-readiness/T-01.3_model-download-step/T-01.3.2_fetch-main-model.md) | Fetch the main model too | code | Done | 28 test cases, 18 of 18 mutations caught, real run 52 s cold and 3 s warm | T-01.3.1, T-01.2.3 | 2026-11-06 |
| 17 | [T-01.4](T-01_deployment-readiness/T-01.4_requirements-split.md) | Split the runtime and dev requirements | code | Done | dev tools and httpx moved to requirements.dev.txt; the contracts 0.16.0 line kept | T-01.1.1 | 2026-11-06 |
| 18 | [T-01.5](T-01_deployment-readiness/T-01.5_service-documents.md) | Service documents true again | docs | Done | nine documents audited; 8 fixed, 160 paths and links checked | T-01.2.3, T-01.3.2, T-01.4 | 2026-11-06 |
| 19 | [T-01.6](T-01_deployment-readiness/T-01.6_pin-runtime-dependencies.md) | Pin the runtime dependencies | code | Done | seven packages pinned; numpy has a Python 3.11 fallback | T-01.4, T-01.1.3, T-01.1.4 | 2026-11-06 |
| 20 | [T-01.7](T-01_deployment-readiness/T-01.7_hide-openai-error-text.md) | Do not echo part of a wrong OpenAI key | code | Done | fixed message; 95 passed; checked with a fake key against the real API | T-01.1.1 | 2026-11-06 |

## B. Deployment tool changes (T-02, the `deployment` repository)

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 21 | [T-02](T-02_deployment-tool-changes/T-02_deployment-tool-changes.md) | Deployment tool changes | epic | Done | built in `deployment` 2026-11-09; fake-shell tests only, no image run | T-02.1 | 2026-11-09 |
| 22 | [T-02.1](T-02_deployment-tool-changes/T-02.1_model-delivery-decision.md) | Decision: how the models reach a container | decision | Done | option B chosen 2026-11-06 (ADR-009) | — | 2026-11-06 |
| 23 | [T-02.2](T-02_deployment-tool-changes/T-02.2_named-volumes.md) | Named volumes for a service | code | Done | `volumes` key, mount in `docker run` | T-02.1 | 2026-11-09 |
| 24 | [T-02.3](T-02_deployment-tool-changes/T-02.3_prepare-in-the-container.md) | Run the `prepare` step against the real settings in Docker | code | Done | `prepare_at_run`, `docker run --rm` between build and start | T-02.2, T-01.3.2 | 2026-11-09 |
| 25 | [T-02.4](T-02_deployment-tool-changes/T-02.4_stt-catalogue-entry.md) | The stt catalogue entry: volume and `HF_HOME` | code | Done | volume, `docker_env` `HF_HOME`, `internal` | T-02.2, T-02.3 | 2026-11-09 |
| 26 | [T-02.5](T-02_deployment-tool-changes/T-02.5_inventory-and-manual.md) | Inventory and manual: the new settings | docs | Done | manual, user guide, README, stt documents | T-01.2.3, T-02.4 | 2026-11-09 |

## C. Docker and arm64 acceptance (T-03)

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 27 | [T-03](T-03_docker-and-arm64-acceptance/T-03_docker-and-arm64-acceptance.md) | Docker and arm64 acceptance | epic | In progress | T-03.1 to T-03.5 done on 2026-11-09; the Pi tasks are postponed | T-01, T-02 | 2026-11-09 |
| 28 | [T-03.1](T-03_docker-and-arm64-acceptance/T-03.1_amd64-build.md) | Build the image on amd64 | manual | Done | run 2026-11-09 on amd64 (see the task) | T-02.4, T-01.4 | 2026-11-09 |
| 29 | [T-03.2](T-03_docker-and-arm64-acceptance/T-03.2_run-and-call.md) | Run the container and call it | manual | Done | run 2026-11-09 on amd64, both engines (see the task) | T-03.1 | 2026-11-09 |
| 30 | [T-03.3](T-03_docker-and-arm64-acceptance/T-03.3_restart-without-redownload.md) | Restart and recreate without a re-download | manual | Done | run 2026-11-09 on amd64 (see the task) | T-03.2 | 2026-11-09 |
| 31 | [T-03.4](T-03_docker-and-arm64-acceptance/T-03.4_image-contents-and-secrets.md) | Image contents and secrets | manual | Done | run 2026-11-09 on amd64 (see the task) | T-03.1 | 2026-11-09 |
| 32 | [T-03.5](T-03_docker-and-arm64-acceptance/T-03.5_first-start-without-network.md) | First start without network | manual | Done | run 2026-11-09 on amd64 (see the task) | T-03.2, T-03.3 | 2026-11-09 |
| 33 | [T-03.6](T-03_docker-and-arm64-acceptance/T-03.6_native-on-a-raspberry-pi.md) | Native on a Raspberry Pi: install and speed | manual | Postponed | needs the Pi (4B, 4 GB, 64-bit, no desktop) | T-01.2.3, T-01.3.2, T-01.4, T-01.1.3 | 2026-11-09 |
| 34 | [T-03.7](T-03_docker-and-arm64-acceptance/T-03.7_docker-on-arm64.md) | Docker on arm64 | manual | Postponed | needs the Pi (4B, 4 GB) with Docker, not known yet | T-03.3, T-03.6 | 2026-11-09 |
| 35 | [T-03.8](T-03_docker-and-arm64-acceptance/T-03.8_record-the-results.md) | Record what was verified | docs | In progress | amd64 part written 2026-11-09; the rest waits for the postponed Pi | T-03.2, T-03.3, T-03.4, T-03.5, T-03.6, T-03.7, T-02.5 | 2026-11-09 |

## D. Recurring

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 36 | [T-04](T-04_documentation-sync.md) | Documentation sync | docs | Recurring | after T-01, T-02 and T-03 | — | 2026-11-06 |

## What can run in parallel

T-01.1.1 to T-01.1.6 are done; now T-01.1.7, T-01.3.1 and T-01.4 do not depend on each other. The chain T-01.3.2 → T-01.5 is ready after T-01.3.1 (T-01.2.2 and T-01.2.3 are done); T-01.3.1 and T-01.4 can run beside it. T-02.2 can start at once (the decision is taken); the first-start timing of T-01.1.2 is attached to ADR-009 when measured. T-01.6 (pinning) waits for the real engine runs. T-01.1.7 and the Pi tasks need hardware.
