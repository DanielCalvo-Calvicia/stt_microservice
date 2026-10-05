# STT Microservice

HTTP service that turns 16-bit mono PCM audio into text, using the OpenAI Whisper API or a local `faster-whisper` model. It segments the audio into utterances by silence detection and answers with `contracts.stream` events. Only Brain calls it.

## Run

```bash
pip install -r requirements.windows.txt   # Linux / Raspberry Pi: requirements.linux.txt
python main.py
```

(Use the service's own venv, `windows\Scripts\python.exe`.) Configuration is read from the environment; a `.env` file next to `main.py` is loaded too (see `.env.example`). The default bind address is `127.0.0.1`; set `SERVICE_HOST` (for example `0.0.0.0`) when Brain runs on another machine.

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_NAME` | `STT Microservice` | API title / log name (the shared logger also reads `SERVICE_NAME`) |
| `SERVICE_HOST` | `127.0.0.1` | Bind address |
| `SERVICE_PORT` | `8001` | Bind port |
| `LOG_LEVEL` | `INFO` | Read by the shared logging module (`TRACE`, `DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`, `CRITICAL`) |
| `STT_ENGINE` | `openai` | `openai` = Whisper API (`whisper-1`); any other value (e.g. `local`) = local faster-whisper (`small.en`, CPU, int8). Case-insensitive |
| `STT_LANGUAGE` | `en` | ISO-639-1 code forced on the transcription (empty falls back to `en`) |
| `STT_PROMPT` | empty | OpenAI engine only: words the model should spell as written (e.g. `Oblivion 306`). Empty = no hint |
| `STT_GATE_ENABLED` | `0` | `1` = also run the wake-phrase gate: a second, local engine under `/gate/...` (see below) |
| `STT_GATE_MODEL` | `tiny.en` | faster-whisper model of the gate (small and fast, run with greedy decoding) |
| `STT_GATE_PROMPT` | `Oblivion 306` | Hint given to the gate engine so it spells the wake phrase right (empty = none) |
| `OPENAI_API_KEY` | *(empty)* | Required when `STT_ENGINE=openai`; startup fails with `EngineNotConfigured` without it. Never log or echo it |

`LOG_FORMAT`, `LOG_OUTPUT`, `ENVIRONMENT` and `TRACE_EXPORT_*` are also read by the shared logging package, not by this service: see [`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md). The table equals `.env.example` and `ServerConfig`/`SttConfig` in `infrastructure/config/`. The engine model names are constants, not settings.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/available` | `data` is `AvailabilityResponse{is_available}`: whether the engine is ready |
| POST | `/process/stream` | Body is raw PCM. Answers with SSE events: `stream_started`, then `partial` + `completed` per utterance |
| POST | `/process/stream/set` | Brain's upload: body is raw PCM, or `contracts.stream` NDJSON events (`Content-Type: application/x-ndjson`, `STT_INBOUND`). Answers with an ack stream (`stream_started`, then `input_completed` when the sender ended, or `error`): SSE by default, NDJSON when `Accept: application/x-ndjson` |
| GET | `/process/stream/get` | Reads the shared stream's text events (`STT_OUTBOUND`): SSE by default, NDJSON with `Accept: application/x-ndjson`; a `heartbeat` every 15 s when idle. 404 if nothing was set |
| POST | `/stop` | Stops the shared stream |
| POST | `/process/batch?sample_rate=16000` | Body is one PCM buffer; `data` is `STTProcessBatchResponse{text}`. 400 if the body is empty |
| POST/GET | `/gate/process/stream/set`, `/gate/process/stream/get` (only with `STT_GATE_ENABLED=1`) | Same as the stream routes, on the gate's own shared stream and local engine. Each `completed` event also carries the utterance's audio in `audio_base64` (PCM16 mono), so Brain can send it to the real engine when the wake phrase was heard. `/gate/available` and `/available` report the gate too |

Stream endpoints take `sample_rate` (16000), `chunk_size` (1024), `silence_threshold` (150) and `silence_limit_seconds` (2.0) as query parameters. Utterances end after `silence_limit_seconds` of silence. On `/process/stream/get` the same names may be repeated but must match the stream that `set` fixed (else 422).

Every `partial` carries the same text as the `completed` after it: the engines only produce finished utterances. Audio is PCM16 mono and is never converted here.

JSON responses use the envelope `action / status / status_code / message / timestamp / data` (`contracts.api.common.envelope.ApiEnvelope`). Failures map to HTTP status codes in `infrastructure/inbound/http/http_error_mapper.py`: `404` no stream set, `422` invalid stream settings or settings that differ from the active stream, `500` anything else (engine or stream failure), and `400` for an empty batch body. There is no authentication.

## Project layout

```text
main.py            entry point (calls main_flow)
main_flow/         .env, config, logging init, uvicorn, graceful shutdown
composition_root/  the only place concrete adapters are wired together (engine choice)
infrastructure/    config, HTTP (inbound: handler, envelope, error mapper, SSE/NDJSON encoding, NDJSON audio decoder) and Whisper engines (outbound)
application/       use-case service, ports, DTOs, application errors
domain/            stream settings, PCM alignment and silence rules
```

Dependencies point inward only (`infrastructure -> application -> domain`); `tests/architecture/` enforces this.

## Development

```powershell
windows\Scripts\python.exe -m pytest        # unit + architecture tests (no model, network or hardware needed)
windows\Scripts\python.exe tests\simple.py  # end to end against a running service
```

Result on 2026-10-01: `93 passed` in 5.4 s. `ruff`, `mypy` and `black` are configured in `pyproject.toml` but are **not installed in this venv**. Running the microphone venv's ruff against this folder reports 9 findings (4 auto-fixable), not fixed on purpose; mypy was not run. The real engines (OpenAI call, faster-whisper model) and `tests/simple.py` were not run in this pass.

Architecture: [docs/architecture/architecture.md](docs/architecture/architecture.md). The previous layout (and the removed autoloader) is archived in [docs/old/](docs/old/).
