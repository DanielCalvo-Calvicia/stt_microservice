import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = ("1", "true", "yes", "on")

# The values the local engine used while they were constants in its code.
_DEFAULT_MODEL = "small.en"
_DEFAULT_THREADS = 2
_DEFAULT_COMPUTE_TYPE = "int8"


def _threads(raw: str) -> int:
    """CPU threads of the local models: blank = default, 0 = let ctranslate2 choose, else a count."""
    text = raw.strip()
    if not text:
        return _DEFAULT_THREADS
    try:
        threads = int(text)
    except ValueError:
        threads = -1
    if threads < 0:
        raise ValueError(
            f"STT_THREADS must be a whole number >= 0 (0 lets ctranslate2 choose), got {raw!r}"
        )
    return threads


@dataclass(slots=True, frozen=True)
class SttConfig:
    engine: str
    language: str
    openai_api_key: str
    prompt: str = ""
    gate_enabled: bool = False
    gate_model: str = "base"
    gate_prompt: str = "Oblivion 306."
    # The local engine: its model, and the CPU threads and compute type of every local model
    # (the gate's too).
    model: str = _DEFAULT_MODEL
    threads: int = _DEFAULT_THREADS
    compute_type: str = _DEFAULT_COMPUTE_TYPE

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "SttConfig":
        return cls(
            engine=env.get("STT_ENGINE", "openai").lower(),
            language=env.get("STT_LANGUAGE", "en").strip() or "en",
            openai_api_key=env.get("OPENAI_API_KEY", ""),
            prompt=env.get("STT_PROMPT", "").strip(),
            gate_enabled=env.get("STT_GATE_ENABLED", "0").strip().lower() in _TRUE,
            gate_model=env.get("STT_GATE_MODEL", "base").strip() or "base",
            gate_prompt=env.get("STT_GATE_PROMPT", "Oblivion 306.").strip(),
            model=env.get("STT_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL,
            threads=_threads(env.get("STT_THREADS", "")),
            compute_type=env.get("STT_COMPUTE_TYPE", _DEFAULT_COMPUTE_TYPE).strip().lower()
            or _DEFAULT_COMPUTE_TYPE,
        )
