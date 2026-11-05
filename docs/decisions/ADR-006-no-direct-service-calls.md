# ADR-006: No autoloader: STT never pulls from another service, Brain coordinates

- **Status:** Accepted and built (commit `19435bf`); a workspace rule.
- **Date:** 2026-09-20.

## Context

STT had an "autoloader" that pulled an audio stream directly from the microphone's URL. That made STT depend on another service's address and format, and made the flow of the robot impossible to read in one place.

## Decision

Services never call each other; Brain is the only coordinator (workspace rule). The autoloader was removed (its code is archived in `docs/old/autoloader/`, as history only). STT has no outbound HTTP call except the OpenAI API of its own engine. Audio reaches it only in the body of a request from Brain.

## Consequences

- STT needs no URL of another service; the deploy tool gives Brain the URL of STT (`STT_BASE_URL`), not the other way round.
- Do not reintroduce a direct pull from the microphone or a push to TTS here. A new interaction is a change in Brain and in `contracts` first.
