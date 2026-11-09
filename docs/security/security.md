# Security

Only what can be verified in the repository. Labels: **Implemented** (in the code and tested), **Configured** (in another repo's configuration), **Required** (the maintainer must do it), **Not implemented**, **Not verified**.

## Access to the service

- **Not implemented:** authentication or authorisation. Every caller uses the same API; the only intended caller is Brain. Service-to-service authentication is not designed in the workspace yet (see `../README.md`).
- **Implemented:** the default bind address is `127.0.0.1`, so a default install is reachable only from the same machine. **Required:** when `SERVICE_HOST` is set to `0.0.0.0` or an address (Brain on another machine), the network in front of port 8001 must limit who can reach it.
- **Not implemented:** CORS (no browsers call the service), TLS (plain HTTP inside the robot's network), rate limits, a limit on the size of a request body or of a stream. A caller can send audio without end; the batch route holds the whole body in memory.
- **Implemented:** `/docs`, `/redoc` and `/openapi.json` are on; they describe the routes only.

## What leaves the machine

- **OpenAI engine (the default):** the audio of **every utterance** is sent to the OpenAI API (as a WAV file), together with the language and the optional `STT_PROMPT`. The API key is sent as the bearer of that call. Anything people say near the microphone and that Brain forwards reaches a third party. The wake-phrase gate exists to cut that: with `STT_GATE_ENABLED=1` and Brain's `WAKE_PHRASE_ENABLED=1` only utterances that carry the phrase are sent on.
- **Local engine and gate:** nothing is sent out; the audio stays on the machine. The models are downloaded from the Hugging Face hub the first time they load.
- **Not implemented:** nothing stores audio or text; the shared stream is in memory.

## Secrets

- **Required:** `OPENAI_API_KEY` is the only secret. It lives in the `.env` file or the environment, never in the code, `.env.example`, a test or a document. In a deployment the deploy tool writes it from `config/local/` (its own repo).
- **Implemented:** `.env` is ignored by git; `.env.example` holds names only. The key is held in the OpenAI engine object and passed to the client; the service does not log or return it on a normal run (two real runs on 2026-11-06 held none). The start fails without it (`EngineNotConfigured`) rather than running with an empty key.
- **Implemented (T-01.7, 2026-11-06):** a failure of the OpenAI call reaches the caller (the `500` answer), the stream's `error` event and the log only as the fixed message `OpenAI request failed: <ErrorType> (HTTP <status>)`, never the library's text; tested with an obviously fake key. History: until then a wrong key came back as the library's `Incorrect API key provided: <first 8 characters>***...<last 4 characters>` in the answer and in the `Operation failed` log line (verified 2026-11-06 in T-01.1.5 drill 5). `/available` still says available with a wrong key (it never calls the API), as documented. The local engine's errors are still the library's text; no secret was found in them.
- **Configured (deployment repo):** in Docker the `.env` is excluded from the build context and bind-mounted read-only, never an image layer. Checked on 2026-11-09 (T-03.4, amd64): 0 matches for `OPENAI_API_KEY` or `sk-` in `docker history`, `docker image inspect`, the running container's `inspect` and the saved layers; the only `.env` entry in the image is `.env.example`; the container's mounts are the `.env` read-only and the models volume. **The container runs as root** (the generic Dockerfile of `deployment` sets no user) and the image holds `docs/`, `tests/` and `CLAUDE.md`: open findings for the `deployment` repository.

## Data handling

- **Implemented:** the logs hold lengths, sample rates and event sequence numbers, never the text or the audio of an utterance.
- **Implemented:** the OpenAI engine's temporary WAV file is removed after the call (also on error); it sits in the system temp folder while the call runs, readable by whoever can read that folder. **Not implemented:** a private temp folder.
- **Implemented:** input is validated before it is used: base64 is decoded with `validate=True` (corrupt audio fails the stream instead of becoming noise), the events follow the `contracts` schema and sequence numbers, an utterance must be whole 16-bit samples at a positive rate, `channels` must be 1.
- **Not implemented:** a limit on utterance length; a very long utterance is transcribed as one batch.

## Supply chain

- **Implemented (T-01.6, 2026-11-08):** the seven packages the service imports are pinned to exact versions in `requirements.windows.txt` and `requirements.linux.txt`: the ones the engines ran with on 2026-11-06. The `numpy` line has a Python 3.11 fallback that is still an open bound (numpy 2.5.4 has no 3.11 build). **Not implemented:** a lock file (the dependencies of those packages are not pinned), dependency scanning. `contracts` comes from a wheel bundled in `vendor/` (reviewed when it is refreshed with `contracts/scripts/bundle.py`).
- **Implemented (T-01.4, 2026-11-08):** pytest, ruff, black, mypy and httpx are in `requirements.dev.txt`, which the deploy tool never installs, so a new deploy does not carry them (a venv built earlier keeps them until it is rebuilt).
- The local models are downloaded from the Hugging Face hub with no checksum check by this service.

## Recommended, not implemented

Authentication shared by the workspace (when it is designed), a request size limit, a timeout and a retry policy for the OpenAI call, a private temp folder, a lock file for the packages the pinned ones depend on (also in the architecture document, *Known debt*).
