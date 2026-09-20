# Constraints

- Input audio is 16-bit mono PCM (odd trailing bytes are held back so no sample is split).
- `STT_ENGINE=openai` needs `OPENAI_API_KEY`; startup fails without it.
- The local engine loads a Whisper model on the CPU at startup (`small.en`, int8).
- There is a single shared stream (`set_stream` / `get_stream`); a new `set_stream` replaces it.
