# CLAUDE.md: stt_microservice

Port **8001**. Python/FastAPI. Speech to text. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

## Role

Brain feeds it audio and reads the text back. STT segments audio by voice activity (silence detection) and transcribes each utterance.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads audio (NDJSON events) |
| `GET /process/stream/get` | Brain reads text events (SSE, or NDJSON with `Accept`) |
| `POST /process/batch?sample_rate=` | One PCM buffer → `{"text": ...}` |
| `GET /health`, `/available`, `POST /stop` | Liveness, readiness, stop |

Engines: `STT_ENGINE=openai` (Whisper API, needs `OPENAI_API_KEY`) or anything else, such as `local` (faster-whisper on CPU). `STT_LANGUAGE` forces the language.

## Layout

`main.py` → `main_flow/` → `composition_root/` → `application/` → `domain/` → `infrastructure/`.

## Rules

- Events use `contracts.stream` (`STT_INBOUND`/`STT_OUTBOUND`) and the shared codec. Never hand-write event JSON.
- The old autoloader (direct pull from another service's stream) was removed on purpose (archived in `docs/old/autoloader/`). Do not reintroduce direct service-to-service calls. Brain coordinates.
- Never log or echo `OPENAI_API_KEY`.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest
```
