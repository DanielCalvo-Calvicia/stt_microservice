# CLAUDE.md: stt_microservice

Port **8001** (`SERVICE_PORT`). Python/FastAPI. Speech to text. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

Current state (2026-10-01): branch `feature_ai_claude_2` (tracks `origin/feature_ai_claude_2`, in sync), working tree clean, last feature commit `650dad1` "Bundle contracts 0.10.0; refresh docs..." (pushed). Tests: `93 passed`. Ruff/mypy are not installed in this venv (the microphone venv's ruff reports 9 findings here, unfixed). Real engines and `tests/simple.py` not run in the last documentation pass.

## Role

Brain feeds it finished utterances and reads the text back. STT does **no** silence detection: the microphone service cuts the audio (silence detection moved there, each treatment is a `MICROPHONE_*` env var) and STT transcribes each utterance as one batch.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads NDJSON events (`STT_INBOUND`: `stream_started`, one `utterance` per utterance; anything else is a 415). Answers with an ack stream that ends in `input_completed` or `error` |
| `GET /process/stream/get` | Brain reads text events (SSE, or NDJSON with `Accept`); heartbeat every 15 s; 404 if nothing was set |
| `POST /process/stream` | Single-request variant (NDJSON `utterance` events in the body, answers SSE). No query settings |
| `POST /process/batch?sample_rate=` | One PCM buffer -> `data: {text}`; 400 on an empty body |
| `/gate/process/stream/{set,get}` | Only with `STT_GATE_ENABLED=1`: the wake-phrase gate, a second local faster-whisper (`STT_GATE_MODEL`, default `tiny.en`, greedy, `STT_GATE_PROMPT` as hint) with its own shared stream. Its `completed` events carry the utterance audio in `audio_base64` (contracts 0.11.0). Brain decides from the text; the real STT only gets `/process/batch` with that audio |
| `GET /health`, `/available`, `POST /stop` | Liveness, engine readiness, stop |

Errors: 404 no stream set, 415 body that is not NDJSON events, 422 invalid utterance, else 500.

Engines: `STT_ENGINE=openai` (default, Whisper API `whisper-1`, needs `OPENAI_API_KEY`) or any other value, such as `local` (faster-whisper `small.en`, CPU int8). `STT_LANGUAGE` forces the language (default `en`). Other env: `SERVICE_NAME/HOST/PORT`, `LOG_LEVEL`. A `.env` next to `main.py` is loaded by `main_flow/http.py`.

## Layout

`main.py` -> `main_flow/` -> `composition_root/` -> `application/` -> `domain/` -> `infrastructure/`. The `input_completed` ack event lives in `contracts.stream.common.input_completed`.

## Rules

- Events use `contracts.stream` (`STT_INBOUND`/`STT_OUTBOUND`, `UPLOAD_ACK`) and the shared codec. Never hand-write event JSON.
- The old autoloader (direct pull from another service's stream) was removed on purpose (archived in `docs/old/autoloader/`). Do not reintroduce direct service-to-service calls. Brain coordinates.
- Never log or echo `OPENAI_API_KEY`. Do not open `.env`.
- `contracts` comes from `vendor/contracts_microservice-<version>.whl` (0.12.0); refresh it with `contracts/scripts/bundle.py`.
- Ruff/mypy/black are configured in `pyproject.toml` but not installed in this venv. Install them first if you need them, and do not bulk-fix lint unasked.
- `.engram/` holds old notes. Do not trust it over the code.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest        # ~5 s, no model/network
```
