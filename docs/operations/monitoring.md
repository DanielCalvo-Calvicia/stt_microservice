# Monitoring and operations

What exists today, checked against the code; anything else is stated as absent.

## Probes

| Probe | Behaviour |
|---|---|
| `GET /health` | `200` with the envelope and `data.healthy = true` whenever the process answers; it touches no engine |
| `GET /available` | `200` with `data.is_available`: the engine is configured/loaded (OpenAI: the key is not empty; local: the model object exists) **and**, with the gate on, the gate's engine too. A failure while checking is a `500` envelope. This is the probe the deploy tool uses for readiness |
| `GET /gate/available` | The gate's own engine (only with `STT_GATE_ENABLED=1`) |

`/available` does not call the OpenAI API: it cannot tell that the key is wrong or the network is down. That shows up as a `500` (batch) or an `error` event (streams) on the first utterance.

## Start-up

`main_flow/http.py` loads `.env`, reads the settings, starts `shared_logging`, builds the container (this loads a local model, or checks the key) and starts uvicorn. A start-up problem stops the process: `EngineNotConfigured` (OpenAI engine without a key), a `ValueError` for a bad `SERVICE_PORT`, a model that cannot be loaded (no network, a mistyped `STT_GATE_MODEL`). A local model can take a while to load or download; the process answers nothing until it is done.

## Shutdown

On `SIGINT` or `SIGTERM` uvicorn stops serving and then `main_flow/http.py` stops the shared stream of the main service and of the gate (a failure to stop one is logged with `stream=shared|gate` and does not stop the other). `Ctrl+C` ends without a traceback.

## Logs

All logging goes through `shared_logging` (`init_logging("stt")`; constant messages with keyword fields; `LOG_LEVEL` decides, `LOG_FORMAT` and `LOG_OUTPUT` are the library's). `TracingMiddleware` is added to the app. What the service writes:

| Level | Message | Fields |
|---|---|---|
| info | `Request received`, `Request completed` (logger `shared_logging.http`, from `TracingMiddleware`) | method, path, client, `status_code`, `duration_ms`; the trace and correlation ids continue the caller's. For a stream route the line is written when the answer ends |
| info | `Starting server`, `Server stopped; stopping the shared stream`, `Cleanup finished` | service name, host, port |
| info | `Creating STT engine`, `Creating the wake-phrase gate engine`, `Loading local Whisper model on CPU`, `Local Whisper model loaded` | engine, language, model name, prompt of the gate |
| info | `Utterance transcribed` | `text_length`, `audio_bytes`, `sample_rate` (never the text) |
| info | `Batch transcription completed`, `OpenAI batch transcription completed`, `Calling OpenAI transcription API` | text length, model, language, `prompted` |
| info | `Decoded STT utterance event`, `Decoded STT completed audio event` | sequence, bytes, sample rate |
| info | `Resampling audio to the Whisper sample rate` | both rates |
| info | `Emitting STT stream heartbeat` | bytes (every 15 s on an idle `get`) |
| info | `Shared stream completed`, `... task cancelled`, `Set stream completed` | none |
| warning | `Get stream rejected`, `Batch request rejected: empty audio body`, `Failed to remove temporary WAV file` | the error / the path |
| error | `Operation failed`, `Input stream failed`, `Shared stream forwarding failed` (with the traceback) | action, error |
| debug | `Received stream chunk`, `Temporary WAV file created/removed` | bytes, path |

The service logs **lengths, never the text and never the audio**. An `Operation failed` line carries the text of the exception; with the OpenAI engine that is the library's error message. Do not assume it is free of anything sensitive (not checked: see [security](../security/security.md)).

## Files on disk

- **OpenAI engine:** each utterance is written to a temporary `.wav` file in the system temp folder, sent to the API and removed in a `finally`. A crash between the two leaves the file; a failed removal is logged as a warning.
- **Local engine:** nothing is written by the service; the models live in the Hugging Face cache (`HF_HOME`, default `~/.cache/huggingface`), tens to hundreds of MB per model.
- No state is kept between restarts: the shared stream is in memory.

## Resources to watch

| What | Why |
|---|---|
| CPU and RAM during a local transcription | the model runs in a worker thread (`asyncio.to_thread`); with a long utterance or a slow CPU (Raspberry Pi) the text arrives late. The speed of a local model on a Pi is **unknown** |
| Time of one OpenAI call | each utterance is a network round trip and a billed call; there is no timeout or retry set by this service beyond the library's defaults |
| Several utterances at once | `set` transcribes the utterances of one stream one after another; the batch route and the gate run concurrently with it |
| Memory of a request | the batch route reads the whole body into memory; there is no size limit |

## Not present

- Metrics, alerting, tracing of the engines' latency: none (the `shared_logging` tracing middleware exists; no dashboard is configured here).
- An audit trail of who called: none (no authentication).
- A health signal for the quality of the transcription: none.
