# Environment variables

All variables are read in two places: `ServerConfig.from_env()` and `SttConfig.from_env()` in `infrastructure/config/`, both called once by `main_flow/http.py` after the `.env` file is loaded. A `.env` next to `main.py` is optional; `load_dotenv` does not override a variable that is already set in the process. The template with comments is [`.env.example`](../../.env.example); the README repeats the main table. **Never write a real secret in `.env.example`, in the code or in a document.**

A bad `SERVICE_PORT` (not a number) stops the start with a `ValueError`. There is no validation of the other values: an unknown `STT_ENGINE` selects the local engine, an unknown `STT_GATE_MODEL` fails when the gate starts (the model cannot be loaded).

## Service

| Variable | Default | Description | Read by | Sensitive |
|---|---|---|---|---|
| `SERVICE_NAME` | `STT Microservice` | API title in `/docs`, name in the logs of the service; also read by `shared_logging` | `ServerConfig`, `shared_logging` | no |
| `SERVICE_HOST` | `127.0.0.1` | Bind address. Set `0.0.0.0` (or an address) when Brain runs on another machine | `ServerConfig` | no |
| `SERVICE_PORT` | `8001` | Bind port | `ServerConfig` | no |
| `LOG_LEVEL` | `INFO` | `TRACE`, `DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`, `CRITICAL` | `shared_logging` | no |

## Engine

| Variable | Default | Description | Read by | Sensitive |
|---|---|---|---|---|
| `STT_ENGINE` | `openai` | `openai` = OpenAI Whisper API (`whisper-1`); any other value (for example `local`) = local faster-whisper. Lower-cased before it is compared | `SttConfig` | no |
| `STT_LANGUAGE` | `en` | ISO-639-1 code forced on the transcription, for both engines and the gate. Empty falls back to `en`. The local `small.en` and the gate's `tiny.en` are English-only models | `SttConfig` | no |
| `OPENAI_API_KEY` | empty | Required when `STT_ENGINE=openai`: the start fails with `EngineNotConfigured` without it. Never log or echo it | `SttConfig` | **yes** |
| `STT_PROMPT` | empty | OpenAI engine only: words the model should spell as written (for example the wake phrase `Oblivion 306`, so it is not written `Obi-Wan 306`). Empty = no hint. Check that it does not make silence come back as these words. Ignored by the local engine | `SttConfig` | no |

## Wake-phrase gate

| Variable | Default | Description | Read by | Sensitive |
|---|---|---|---|---|
| `STT_GATE_ENABLED` | `0` | `1`, `true`, `yes` or `on` = also run the gate: a small local model under `/gate/...`. Brain needs `WAKE_PHRASE_ENABLED=1` to use it | `SttConfig` | no |
| `STT_GATE_MODEL` | `tiny.en` | faster-whisper model of the gate (`tiny.en` is the fastest, `base.en` more accurate; English only). Runs with greedy decoding (`beam_size=1`) | `SttConfig` | no |
| `STT_GATE_PROMPT` | `Oblivion 306` | Text that biases the gate's model toward the wake phrase; use the same words as Brain's `WAKE_PHRASE`. Empty = no hint | `SttConfig` | no |

## Not settings (constants in the code)

These are **not** configurable today. The audit of 2026-11-04 ([deployment_audit/stt.md](../deployment_audit/stt.md)) recommends making the first three settings; that is **Planned**, not built.

| Constant | Value | Where |
|---|---|---|
| Main local model | `small.en` (English only) | `DEFAULT_MODEL_NAME` in `local_whisper_transcription.py` |
| Device, compute type, threads of a local model (main and gate) | `cpu`, `int8`, `cpu_threads=2` | `LocalWhisperTranscription.__init__` |
| Local decoding | `beam_size` 5 (gate: 1), `condition_on_previous_text=False`, `no_speech_threshold=0.65` | `local_whisper_transcription.py` |
| OpenAI model and temperature | `whisper-1`, `temperature=0.0`, `response_format="text"` | `openai_whisper_transcription.py` |
| Heartbeat of `GET .../get` | 15 s | `_GET_HEARTBEAT_SECONDS` in `http_handler.py` |
| Default batch sample rate | 16000 | `_DEFAULT_BATCH_SAMPLE_RATE` in `http_handler.py` |
| Gate route prefix | `/gate` (Brain's `STT_GATE_PATH_PREFIX` must match) | `GATE_PREFIX` in `http_handler.py` |
| Keep-alive of the server | 60 s | `main_flow/http.py` |

## Read by libraries, not by this service

| Variable | Used by | Meaning |
|---|---|---|
| `LOG_FORMAT`, `LOG_OUTPUT`, `ENVIRONMENT`, `TRACE_EXPORT_*` | `shared_logging` | See [`shared-logging/docs/logging.md`](../../../shared-logging/docs/logging.md) |
| `HF_HOME` | `huggingface_hub` (through faster-whisper) | Cache of the downloaded models, default `~/.cache/huggingface`. Not read by the service; set it in the environment or `.env`. A value in `.env` takes effect because the engine module is imported after `load_dotenv` |
| `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, proxy variables | the `openai` and `httpx` libraries | Honoured if set in the environment; not documented or tested here |

## Who sets them in a deployment

`deployment/` owns the real values: `config/services/stt.toml` (the inventory of this table), `config/local/` for the key, and `docs/DEPLOYMENT.md` for the manual. After any change to `.env.example` run `brain_microservice\windows\Scripts\python.exe deployment\scripts\env_inventory.py --write` from the workspace root and update the stt table of the manual (another repo). The catalogue sets `STT_ENGINE=openai` and requires `OPENAI_API_KEY` when the engine is `openai`. The URL where Brain finds this service (`STT_BASE_URL`) is Brain's setting, computed by the deploy tool, not a variable of this service.
