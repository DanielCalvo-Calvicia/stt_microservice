# Architecture

STT Microservice follows the same Clean Architecture layout as `microphone_microservice`.
It supersedes the README in `docs/old/`. Reviewed against the code on 2026-10-01 (branch `feature_ai_claude_2`).

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
                              domain: AudioUtterance, Utterance
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
  errors.py                       DomainError, InvalidAudioUtterance
  value_objects/audio_utterance.py AudioUtterance(audio, sample_rate): whole 16-bit samples at a positive rate
  value_objects/utterance.py     Utterance(text, audio): what the wake-phrase gate's stream yields
application/
  errors.py                       ApplicationError, NoActiveStream, SharedStreamForwardingError, EngineNotConfigured, UnsupportedInput
  dtos/                           ProcessStreamInboundDTO, SetStreamInboundDTO, ProcessBatchInboundDTO,
                                  TextStreamOutboundDTO, BatchTranscriptionOutboundDTO
  ports/inbound/stt_transcription_port.py   SttTranscriptionPort (driving)
  ports/outbound/transcription_port.py      TranscriptionPort (driven)
  services/stt_service.py         SttService — transcribes each utterance, owns the shared stream, no rules of its own
infrastructure/
  config/                         ServerConfig, SttConfig (env -> frozen dataclasses)
  inbound/http/                   http_handler.py (SttHandler), http_envelope.py, http_error_mapper.py,
                                  stream_events.py (SSE/NDJSON encoding), input_stream_response.py,
                                  ndjson_audio_input.py (STT inbound contract events -> utterances)
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

* **Contract streams (since the 2026-09-20 commit).** Text leaves as `contracts.stream` events (`STT_OUTBOUND`: `stream_started`, a `partial` and a `completed` per utterance, `heartbeat` every 15 s on `/process/stream/get`, `error`); audio can arrive as `STT_INBOUND` NDJSON events; the upload request answers with the `UPLOAD_ACK` stream (`stream_started`, `input_completed` or `error`). SSE is the default framing, NDJSON on `Accept: application/x-ndjson`.
* **Natural HTTP statuses.** `http_error_mapper.py`: 404 no stream set, 422 invalid settings or settings that differ from the active stream, else 500; empty batch body 400.
* The autoloader (STT pulling a stream from another service) was removed; its old code is archived in `docs/old/autoloader/`.

* `StreamSettings` rejects a non-positive `sample_rate`/`chunk_size` and negative silence values up front;
  before, `chunk_size=0` failed with a `ZeroDivisionError` deep inside the stream.
* `POST /process/batch` with an empty body now returns **400**. The old code raised `HTTPException(400)` inside
  a `try/except Exception`, so it was actually returned as a 500.
* `NoActiveStream` (was a bare `RuntimeError`) maps to 404 by type instead of catching every `RuntimeError`.

## Known remaining debt

1. (Resolved) `InvalidStreamSettings` and `StreamSettingsMismatch` now map to 422; unexpected failures stay 500.
2. The OpenAI engine's start-of-speech threshold is based on the quietest chunk seen so far, so audio that is
   loud from the very first chunk is not detected as speech until a quieter chunk lowers that floor.
3. The local model (`small.en`) and the OpenAI model (`whisper-1`) are constants, not configuration.
4. `tests/simple.py` is an end-to-end script that needs a running service and real audio.

## 2026-10-05: silence detection moved to the microphone

STT no longer cuts audio into utterances. `StreamSettings`, `PcmChunkAligner`, the silence rules and both engines'
voice-activity loops (the OpenAI engine's noise-floor tracking, the local engine's DC-offset removal) are gone from
here; they live in `microphone_microservice` (`UtteranceSegmenter`, `InputTreatment`), each treatment switched on or off
by its own `MICROPHONE_*` variable. The microphone sends one `utterance` event per utterance (contracts 0.12.0), Brain
relays it as an STT inbound `utterance` event, and an engine is now only `transcribe_batch` + `is_available`. The stream
routes take no query settings; a raw-PCM upload is a 415. The wake-phrase gate's engine is an ordinary engine: the
service itself pairs each text with the audio it came from.
