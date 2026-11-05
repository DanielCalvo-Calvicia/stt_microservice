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
- **Implemented:** `.env` is ignored by git; `.env.example` holds names only. The key is held in the OpenAI engine object and passed to the client; the service never logs or returns it. The start fails without it (`EngineNotConfigured`) rather than running with an empty key.
- **Not verified:** that a failure text from the OpenAI library never contains part of a key; the service returns `str(error)` in the failure envelope and logs it (`Operation failed`). Do not rely on it being clean.
- **Configured (deployment repo):** in Docker the `.env` is excluded from the build context and bind-mounted read-only, never an image layer. `docker history` / `docker inspect` were not checked.

## Data handling

- **Implemented:** the logs hold lengths, sample rates and event sequence numbers, never the text or the audio of an utterance.
- **Implemented:** the OpenAI engine's temporary WAV file is removed after the call (also on error); it sits in the system temp folder while the call runs, readable by whoever can read that folder. **Not implemented:** a private temp folder.
- **Implemented:** input is validated before it is used: base64 is decoded with `validate=True` (corrupt audio fails the stream instead of becoming noise), the events follow the `contracts` schema and sequence numbers, an utterance must be whole 16-bit samples at a positive rate, `channels` must be 1.
- **Not implemented:** a limit on utterance length; a very long utterance is transcribed as one batch.

## Supply chain

- **Not implemented:** version pins (`>=` only), a lock file, dependency scanning. `contracts` comes from a wheel bundled in `vendor/` (reviewed when it is refreshed with `contracts/scripts/bundle.py`).
- **Known debt:** pytest, ruff, black and mypy are in the runtime requirement files and so are installed in the deployed image (a larger attack surface than needed).
- The local models are downloaded from the Hugging Face hub with no checksum check by this service.

## Recommended, not implemented

Authentication shared by the workspace (when it is designed), a request size limit, a timeout and a retry policy for the OpenAI call, a private temp folder, pinned dependencies, moving the dev tools out of the runtime requirements (also in the architecture document, *Known debt*).
