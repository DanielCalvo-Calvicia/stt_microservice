# Project

STT Microservice: HTTP service that turns 16-bit mono PCM audio into text, with OpenAI Whisper or a
local faster-whisper model.

Intentionally omitted from the Engram tree (add only when needed): `.devcontainer/`, `.github/`,
`k8s/`, `Dockerfile`, `docker-compose.yml`, `domain/entities/` (the shared stream's state lives in
the application service, not in a business entity).
