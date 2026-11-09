# Environment variables

All variables are read in two places: `ServerConfig.from_env()` and `SttConfig.from_env()` in `infrastructure/config/`, both called once by `main_flow/http.py` after the `.env` file is loaded. A `.env` next to `main.py` is optional; `load_dotenv` does not override a variable that is already set in the process. The template with comments is [`.env.example`](../../.env.example); the README repeats the main table. **Never write a real secret in `.env.example`, in the code or in a document.**

A bad `SERVICE_PORT` (not a number) or a bad `STT_THREADS` (not a whole number `>= 0`) stops the start with a `ValueError`. There is no validation of the other values (a model or compute type name that is wrong fails when the model loads): an unknown `STT_ENGINE` selects the local engine, an unknown `STT_GATE_MODEL` fails when the gate starts (the model cannot be loaded).

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
| `STT_LANGUAGE` | `en` | ISO-639-1 code forced on the transcription, for both engines and the gate. Empty falls back to `en`. The default local `small.en` is an English-only model: for another language set `STT_MODEL` to a multilingual one (the gate's default `base` already is) | `SttConfig` | no |
| `OPENAI_API_KEY` | empty | Required when `STT_ENGINE=openai`: the start fails with `EngineNotConfigured` without it. Never log or echo it | `SttConfig` | **yes** |
| `STT_PROMPT` | empty | OpenAI engine only: words the model should spell as written (for example the wake phrase `Oblivion 306`, so it is not written `Obi-Wan 306`). Empty = no hint. Check that it does not make silence come back as these words. Ignored by the local engine | `SttConfig` | no |

## Local engine

The settings of the local models (decision: [ADR-008](../decisions/ADR-008-local-model-settings.md)), used by the main local model and, for the threads and the compute type, by the gate too (the gate keeps its own model name, `STT_GATE_MODEL`). Built in T-01.2.2 and T-01.2.3 (2026-11-08) and unit-tested with a fake model; a non-default value was not run with a real model.

| Variable | Default | Description | Read by | Sensitive |
|---|---|---|---|---|
| `STT_MODEL` | `small.en` | faster-whisper model of the local engine (any `STT_ENGINE` other than `openai`). `small.en` is English only; for another language use a multilingual one (`small`, `base`, `medium`...) with `STT_LANGUAGE`. Blank = the default | `SttConfig` | no |
| `STT_THREADS` | `2` | CPU threads of every local model, the main one and the gate's. `0` = let ctranslate2 choose. Blank = the default. A value that is not a whole number `>= 0` stops the start with a `ValueError` naming `STT_THREADS` | `SttConfig` | no |
| `STT_COMPUTE_TYPE` | `int8` | Compute type of every local model (`int8` is the fastest on a CPU, `float32` the most exact). Trimmed and lower-cased, blank = the default. Passed to ctranslate2 as given: an unsupported name fails when the model loads | `SttConfig` | no |

## Wake-phrase gate

| Variable | Default | Description | Read by | Sensitive |
|---|---|---|---|---|
| `STT_GATE_ENABLED` | `0` | `1`, `true`, `yes` or `on` = also run the gate: a small local model under `/gate/...`. Brain needs `WAKE_PHRASE_ENABLED=1` to use it | `SttConfig` | no |
| `STT_GATE_MODEL` | `base` | faster-whisper model of the gate (default changed from `tiny.en` on 2026-11-09, see ADR-005). `base` is multilingual and caught the wake phrase far more often than `tiny.en` on a real microphone at about 0.6 s per clip on a PC; `small.en` is more exact and about three times slower. The `.en` models are English only. Runs with greedy decoding (`beam_size=1`) | `SttConfig` | no |
| `STT_GATE_PROMPT` | `Oblivion 306.` | Text that biases the gate's model toward the wake phrase. Give it the name **and the code**, as in Brain's `WAKE_PHRASE` (default `Oblivion 306`): with only the name the gate heard the phrase far less often. Empty = no hint | `SttConfig` | no |

## Not settings (constants in the code)

These are **not** configurable. The model, the compute type and the threads of a local model were constants here until T-01.2.3 (2026-11-08); they are the settings of "Local engine" above now ([ADR-008](../decisions/ADR-008-local-model-settings.md)).

| Constant | Value | Where |
|---|---|---|
| Device of a local model (main and gate) | `cpu` | `LocalWhisperTranscription.__init__` |
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
| `HF_HOME` | `huggingface_hub` (through faster-whisper) | Cache of the downloaded models, default `~/.cache/huggingface`. Not read by the service; set it in the environment or `.env`. A value in `.env` takes effect because the engine module is imported after `load_dotenv` (checked on 2026-11-06: the deploy tool wrote it to the `.env` and the models were downloaded to that folder) |
| `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, proxy variables | the `openai` and `httpx` libraries | Honoured if set in the environment; not documented or tested here |

## Who sets them in a deployment

`deployment/` owns the real values: `config/services/stt.toml` (the inventory of this table), `config/local/` for the key, and `docs/DEPLOYMENT.md` for the manual. After any change to `.env.example` run `brain_microservice\windows\Scripts\python.exe deployment\scripts\env_inventory.py --write` from the workspace root and update the stt table of the manual (another repo). The catalogue sets `STT_ENGINE=openai` and requires `OPENAI_API_KEY` when the engine is `openai`. The URL where Brain finds this service (`STT_BASE_URL`) is Brain's setting, computed by the deploy tool, not a variable of this service.
