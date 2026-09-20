# Decisions

- D1: No `cmd/` folder (shadows stdlib `cmd`); entry point is `main.py` + `main_flow/`.
- D2: Config is stdlib frozen dataclasses in `infrastructure/config/`.
- D3: One outbound `TranscriptionPort` serves both engines (stream, batch, availability).
- D4: HTTP status mapping stays "everything is 500" except `NoActiveStream` -> 404 (`http_error_mapper.py`).
- D5: SSE/NDJSON event formatting and NDJSON audio decoding are transport, so they live in `infrastructure/inbound/http`.
- D6: `StreamSettings` validates at the application boundary; invalid settings fail fast instead of dividing by zero inside a stream.
- D7: Runtime environments (`APP_ENV` log levels, `runtime/`) were dropped; logging is stdlib and `LOG_LEVEL` decides.
- D8: Engine modules are imported lazily by the composition root, so the unused engine's library is never loaded.
