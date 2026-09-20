# STT Microservice

HTTP service that turns 16-bit mono PCM audio into text, using the OpenAI Whisper API or a local
`faster-whisper` model.

## Run

```bash
pip install -r requirements.windows.txt
python main.py
```

Configuration is read from the environment (a `.env` file next to `main.py` is loaded); see `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_NAME` | `STT Microservice` | API title / log name |
| `SERVICE_HOST` | `127.0.0.1` | Bind address |
| `SERVICE_PORT` | `8001` | Bind port |
| `LOG_LEVEL` | `INFO` | Read by the shared logging module; `TRACE`→DEBUG, `WARN`→WARNING also accepted |
| `LOG_FORMAT`, `SERVICE_NAME`, `TRACE_EXPORT_*` | see docs | Also read by the shared logging module: [`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md) |
| `STT_ENGINE` | `openai` | `openai` = Whisper API; anything else = local faster-whisper (`small.en`, CPU, int8) |
| `STT_LANGUAGE` | `en` | ISO-639-1 code forced on the transcription |
| `OPENAI_API_KEY` | *(empty)* | Required when `STT_ENGINE=openai`; startup fails without it |

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/available` | `true` if the engine is ready |
| POST | `/process/stream` | Body is raw PCM. Answers with SSE events: `stream_started`, then `partial` + `completed` per utterance |
| POST | `/process/stream/set` | Feeds the shared stream. Body is raw PCM, or NDJSON events (`Content-Type: application/x-ndjson`) |
| GET | `/process/stream/get` | Reads the shared stream's text as SSE (or NDJSON with `Accept: application/x-ndjson`). 404 if nothing was set |
| POST | `/stop` | Stops the shared stream |
| POST | `/process/batch?sample_rate=16000` | Body is one PCM buffer; returns `{"text": ...}`. 400 if the body is empty |

Stream endpoints take `sample_rate` (16000), `chunk_size` (1024), `silence_threshold` (150) and
`silence_limit_seconds` (2.0) as query parameters. Utterances end after `silence_limit_seconds` of
silence. Both must be positive/non-negative or the request fails with 500.

JSON responses use the envelope `action / status / status_code / message / timestamp / data`.
Every failure currently returns HTTP 500, except "no stream set" (404) and an empty batch (400).

## Project layout

```text
main.py            entry point (calls main_flow)
main_flow/         startup and graceful shutdown (logging: shared `shared_logging` package)
composition_root/  the only place concrete adapters are wired together
infrastructure/    config, HTTP (inbound) and Whisper engines (outbound)
application/       use-case service, ports, DTOs, application errors
domain/            stream settings, PCM alignment and silence rules
```

Dependencies point inward only (`infrastructure → application → domain`); `tests/architecture/`
enforces this.

## Development

```bash
pytest                    # unit + architecture tests (no model, network or hardware needed)
mypy .
ruff check .
black --check .
python tests/simple.py    # end-to-end against a running service
```

Architecture: [docs/architecture/architecture.md](docs/architecture/architecture.md).
The previous layout is documented in [docs/old/](docs/old/).
