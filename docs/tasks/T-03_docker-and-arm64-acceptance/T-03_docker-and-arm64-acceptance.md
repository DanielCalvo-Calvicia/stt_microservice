# T-03 — Docker and arm64 acceptance

| | |
|---|---|
| Status | in-progress (T-03.1 to T-03.5 done 2026-11-09; T-03.6 and T-03.7 postponed; T-03.8 half written) |
| Kind | epic |
| Depends on | T-01, T-02 |
| Blocks | — |

## Goal

Prove, on real systems, the things the audit could only read: the Docker image of stt builds without the dev tools or any secret, a local model survives a restarted and a recreated container, a first start without network fails the way the documents say, and the service installs and runs natively and in Docker on arm64 (a Raspberry Pi 4 or newer) at a usable speed. Nothing in this epic has ever been run (NFR-9, NFR-11, the "Not yet verified" list of [../../deployment/deployment.md](../../deployment/deployment.md)).

## Preconditions (the assistant checks them first and stops if one fails)

- **Docker is running** on the machine where the image is built. On the maintainer's PC Docker Desktop answered on 2026-11-06 (`desktop-linux`, linux/x86_64, F17); check again with `docker --context desktop-linux info`.
- **The Docker CLI context.** The saved context here is `desktop-linux`; `raspberry` is an SSH context to the Pi. Every `docker` command in this epic names its context (`docker --context desktop-linux ...` for the PC, `docker --context raspberry ...` for T-03.7), and the saved context is never changed. The deployment tool calls plain `docker`, so before running it for a Docker deploy confirm which context is active (`docker context ls` marks it with `*`).
- **The tool deploys the pushed branch.** `deploy` clones `feature_ai_claude_2` from the remote named in the catalogue, so the T-01 changes are not in a Docker image until the maintainer has committed and pushed them (the assistant does not commit or push unasked). To test unpushed work, the maintainer can point `git` of stt in their own `deployment/config/local/stt.toml` at a local checkout (the header of `config/services/stt.toml` says how); say which source a run used. The working folder also has the uncommitted `contracts` 0.16.0 edit (F1).
- **Network and disk:** the base image, pip packages and the models (about the size of `small.en` and `tiny.en`, hundreds of MB, plus an image of about a gigabyte). Say so and wait for a yes before the first build or download.
- **Secrets:** a real `OPENAI_API_KEY` is used only through the maintainer's git-ignored `deployment/config/local/` files and is never printed, copied or pasted. Checks look for the **absence** of key names and `sk-` prefixes in command output; they never echo a value.
- Build from the tool (which clones), never from the working folder.

## Subtasks

| Order | Task | Kind | State |
|---|---|---|---|
| 1 | [T-03.1 Build the image on amd64](T-03.1_amd64-build.md) | manual | done |
| 2 | [T-03.2 Run the container and call it](T-03.2_run-and-call.md) | manual | done |
| 3 | [T-03.3 Restart and recreate without a re-download](T-03.3_restart-without-redownload.md) | manual | done |
| 4 | [T-03.4 Image contents and secrets](T-03.4_image-contents-and-secrets.md) | manual | done |
| 5 | [T-03.5 First start without network](T-03.5_first-start-without-network.md) | manual | done |
| 6 | [T-03.6 Native on a Raspberry Pi: install and speed](T-03.6_native-on-a-raspberry-pi.md) | manual | postponed |
| 7 | [T-03.7 Docker on arm64](T-03.7_docker-on-arm64.md) | manual | postponed |
| 8 | [T-03.8 Record what was verified](T-03.8_record-the-results.md) | docs | in-progress |

## Exit criteria

Each leaf has its observed result (or exact failure) in *Notes*; `docs/deployment/deployment.md` ("Docker", "Portability" and a new "Verified deployments" section) names what was run, on which machine and architecture, and what was not; NFR-9 and NFR-11 show the real status.

## Maintainer's answers (2026-11-06, [Q01](../../questionnaires/Q01_before-the-deployment-tasks.md))

- **Docker on this PC (question 15):** the assistant may use it for T-03 once T-02 is done, with throw-away containers and volumes that it removes afterwards, **only the ones it created**. The model, the volume `oblivion-stt-models` of the real deploy and any container of the maintainer are not touched. The first build still waits for a yes after the size is said (the preconditions above).
- **The Pi (question 14):** 4B, 4 GB, 64-bit Raspberry Pi OS without a desktop; Docker on it and the `raspberry` context are not known yet.
- **Decision T-02.1:** option B, so the volume, the run-time `prepare` and the restart without a re-download are all in scope ([ADR-009](../../decisions/ADR-009-model-delivery-in-docker.md)).
