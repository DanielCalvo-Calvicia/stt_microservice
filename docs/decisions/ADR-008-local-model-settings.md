# ADR-008: The model, the threads and the compute type of the local models are settings

- **Status:** Accepted and built: the settings are read into `SttConfig` (T-01.2.2, 2026-11-06) and used by the main model and the gate (T-01.2.3, 2026-11-08).
- **Date:** 2026-11-06 (decided by the maintainer in chat, recorded as decision T-01.2.1).

## Context

The local engine had its model, compute type and thread count as constants in `LocalWhisperTranscription`: `small.en`, `int8`, `cpu_threads=2`. The wake-phrase gate runs on the same class, so it shared them. Two consequences: `STT_LANGUAGE=es` cannot work with the local engine, because `small.en` is English only; and a Raspberry Pi cannot be tuned (more or fewer threads, another model) without editing code. The maintainer plans Spanish for the future and runs the robot on a Raspberry Pi 4B with 4 GB. The deployment audit of 2026-11-04 recommended making them settings.

Options considered ([T-01.2.1](../tasks/T-01_deployment-readiness/T-01.2_local-model-settings/T-01.2.1_settings-decision.md)): (A) three settings, the threads and the compute type shared by the main model and the gate; (B) A plus separate gate settings; (C) A with a bad value silently replaced by the default.

## Decision

Option A:

- **`STT_MODEL`**: the model of the local engine (the main one). Default `small.en`. Blank means the default.
- **`STT_THREADS`**: CPU threads of every local model, the main one and the gate's. Default `2`. Blank means the default. `0` is valid and lets ctranslate2 choose. A value that is not a whole number `>= 0` stops the start with a `ValueError` that names `STT_THREADS` and the text it got, as a bad `SERVICE_PORT` does.
- **`STT_COMPUTE_TYPE`**: compute type of every local model. Default `int8`. Trimmed and lower-cased; blank means the default. It is passed to ctranslate2 as given: the service keeps no list of valid names (they depend on the CPU and the ctranslate2 version), so an unsupported one fails when the model loads.
- The OpenAI model stays the constant `whisper-1`. The device stays `cpu`. The gate keeps its own `STT_GATE_MODEL`, with the shared threads and compute type.

## Consequences

- With none of the three set, nothing changes: `small.en`, `int8`, 2 threads, the gate's `tiny.en`.
- Moving to Spanish is a settings change (`STT_MODEL` to a multilingual model such as `small`, and `STT_LANGUAGE=es`), not a code change.
- The gate cannot get a different thread count than the main model. Separate gate settings (option B) can be added later without renaming anything: the shared values would be their defaults.
- A typo in a thread count is caught at start; a typo in a model or compute type name is caught when the model loads (a download or a ctranslate2 error), as the gate's model name already was.
- The deployment tool lists the three settings (`deployment/config/services/stt.toml`, generated from `.env.example`); its manual changes in T-02.5.
- Unit-tested with a fake `WhisperModel` (what the model receives, for the main model and the gate). A non-default value has not been run with a real model; the speed on a Raspberry Pi with other values is measured in T-03.6.
