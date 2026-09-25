# CLAUDE.md: stt_microservice

Port **8001**. Python/FastAPI. Speech to text. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

Current state (2026-09-22): branch `feature_ai_claude`, clean, last commit "STT: contract events, input_completed ack, format and settings validation, remove autoloader".

## Role

Brain feeds it audio and reads the text back. STT segments audio by voice activity (silence detection) and transcribes each utterance.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads audio (NDJSON events). Answers with an ack stream that ends in `input_completed` or `error` |
| `GET /process/stream/get` | Brain reads text events (SSE, or NDJSON with `Accept`) |
| `POST /process/stream` | Single-request variant (audio in the body, `sample_rate`, `chunk_size`, `silence_threshold`, `silence_limit_seconds` as query params) |
| `POST /process/batch?sample_rate=` | One PCM buffer → `{"text": ...}` |
| `GET /health`, `/available`, `POST /stop` | Liveness, readiness, stop |

Engines: `STT_ENGINE=openai` (default, Whisper API, needs `OPENAI_API_KEY`) or any other value, such as `local` (faster-whisper on CPU). `STT_LANGUAGE` forces the language. Other env: `SERVICE_NAME/HOST/PORT`, `LOG_LEVEL`.

## Layout

`main.py` → `main_flow/` → `composition_root/` → `application/` → `domain/` → `infrastructure/`. The `input_completed` ack event lives in `contracts.stream.common.input_completed`.

## Rules

- Events use `contracts.stream` (`STT_INBOUND`/`STT_OUTBOUND`) and the shared codec. Never hand-write event JSON.
- The old autoloader (direct pull from another service's stream) was removed on purpose (archived in `docs/old/autoloader/`). Do not reintroduce direct service-to-service calls. Brain coordinates.
- Never log or echo `OPENAI_API_KEY`.
- Ruff/mypy are configured in `pyproject.toml` but not installed in this venv. Install them first if you need them, and do not bulk-fix lint unasked.
- `.engram/` holds old notes. Do not trust it over the code.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest
```
