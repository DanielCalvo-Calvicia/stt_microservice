# Architecture

STT Microservice follows the same Clean Architecture layout as `microphone_microservice`.
It supersedes the README in `docs/old/`.

## Layers and dependency rule

```
composition_root  ──▶  infrastructure  ──▶  application  ──▶  domain
 (chooses concretes)    inbound/outbound     ports+services    value objects, operations
```

Source-code dependencies point inward only. Runtime calls go outward (HTTP → service → engine)
through ports owned by `application`.

```
SttHandler ──▶ SttTranscriptionPort ◀── SttService ──▶ TranscriptionPort ◀── OpenAIWhisperTranscription
(inbound)      (driving port)           (application)    (driven port)    ◀── LocalWhisperTranscription
                                             │                                   (outbound)
                                             ▼
                              domain: StreamSettings, PcmChunkAligner, silence rules
```

`tests/architecture/test_dependency_rules.py` enforces this by parsing imports:

| Layer | May import | Must not import |
|---|---|---|
| `domain` | stdlib, `domain` | everything else |
| `application` | stdlib, `domain`, `application` | `infrastructure`, `composition_root`, fastapi/starlette/pydantic/uvicorn/numpy/httpx/dotenv/openai/faster_whisper |
| `infrastructure/inbound` | application, domain, frameworks | `infrastructure.outbound`, `composition_root` |
| `infrastructure/outbound` | application, domain, frameworks | `infrastructure.inbound`, `composition_root` |
| `composition_root` | everything | — |
| `main_flow` | `composition_root`, `infrastructure.config` | `infrastructure.inbound`, `infrastructure.outbound` |

## Layout

```
main.py                           calls main_flow.http.run_http()
main_flow/
  http.py                         .env -> config -> container -> uvicorn -> shutdown cleanup
domain/
  errors.py                       DomainError, InvalidStreamSettings
  value_objects/stream_settings.py StreamSettings(sample_rate, chunk_size, silence_threshold, silence_limit_seconds)
  operations/pcm.py               PcmChunkAligner: never split a 16-bit sample across chunks
  operations/silence.py           silence_limit_chunks, silence_boundary_chunks
application/
  errors.py                       ApplicationError, NoActiveStream, SharedStreamForwardingError, EngineNotConfigured
  dtos/                           ProcessStreamInboundDTO, SetStreamInboundDTO, ProcessBatchInboundDTO,
                                  CompletedAudioSegment, TextStreamOutboundDTO, BatchTranscriptionOutboundDTO
  ports/inbound/stt_transcription_port.py   SttTranscriptionPort (driving)
  ports/outbound/transcription_port.py      TranscriptionPort (driven)
  services/stt_service.py         SttService — validates settings, owns the shared stream, no rules of its own
infrastructure/
  config/                         ServerConfig, SttConfig (env -> frozen dataclasses)
  inbound/http/                   http_handler.py (SttHandler), http_envelope.py, http_error_mapper.py,
                                  stream_events.py (SSE/NDJSON encoding), input_stream_response.py,
                                  ndjson_audio_input.py (STT inbound contract events -> audio)
  outbound/openai_whisper/        openai_whisper_transcription.py
  outbound/local_whisper/         local_whisper_transcription.py
composition_root/
  dependencies/stt_dependencies.py       new_transcription / new_stt_service / new_http_app
  containers/http_container.py           HttpContainer, new_http_container
tests/  domain/ application/ infrastructure/ composition_root/ architecture/   (pytest)   +   simple.py (e2e)
```

## What changed from the previous layout

* `application/dtos/mapper/` is gone: the inbound, service and outbound DTO triples were field-for-field
  copies. There is now one DTO per use case; the two engines share one `TranscriptionPort`.
* The engines' duplicated odd-byte handling became `domain.operations.pcm.PcmChunkAligner`, and the silence
  arithmetic (also duplicated in the HTTP adapter) became `domain.operations.silence`.
* `runtime/` (custom logger with per-environment levels, VS Code launch-profile parsing) is replaced by
  the shared `shared_logging` package (`init_logging("stt")` in `main_flow/http.py`); `LOG_LEVEL` decides. `APP_ENV` is no longer read. Per-chunk `trace` logging is now `debug`.
* The 660-line `fastapi_adapter.py` is split into handler, SSE/NDJSON encoding, upload response, NDJSON audio
  decoder. It no longer doubles as an inbound port.
* Engine modules are imported lazily, so running with `openai` no longer loads `faster-whisper` (and vice versa).

## Deliberate changes

* `StreamSettings` rejects a non-positive `sample_rate`/`chunk_size` and negative silence values up front;
  before, `chunk_size=0` failed with a `ZeroDivisionError` deep inside the stream.
* `POST /process/batch` with an empty body now returns **400**. The old code raised `HTTPException(400)` inside
  a `try/except Exception`, so it was actually returned as a 500.
* `NoActiveStream` (was a bare `RuntimeError`) maps to 404 by type instead of catching every `RuntimeError`.

## Known remaining debt

1. Domain errors are not mapped to 4xx (`InvalidStreamSettings` → 422); see `http_error_mapper.py`, decision D4.
2. The OpenAI engine's start-of-speech threshold is based on the quietest chunk seen so far, so audio that is
   loud from the very first chunk is not detected as speech until a quieter chunk lowers that floor.
3. The local model (`small.en`) and the OpenAI model (`whisper-1`) are constants, not configuration.
4. `tests/simple.py` is an end-to-end script that needs a running service and real audio.
