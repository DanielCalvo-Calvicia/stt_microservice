import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = ("1", "true", "yes", "on")


@dataclass(slots=True, frozen=True)
class SttConfig:
    engine: str
    language: str
    openai_api_key: str
    gate_enabled: bool = False
    gate_model: str = "tiny.en"
    gate_prompt: str = "Oblivion 306"

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "SttConfig":
        return cls(
            engine=env.get("STT_ENGINE", "openai").lower(),
            language=env.get("STT_LANGUAGE", "en").strip() or "en",
            openai_api_key=env.get("OPENAI_API_KEY", ""),
            gate_enabled=env.get("STT_GATE_ENABLED", "0").strip().lower() in _TRUE,
            gate_model=env.get("STT_GATE_MODEL", "tiny.en").strip() or "tiny.en",
            gate_prompt=env.get("STT_GATE_PROMPT", "Oblivion 306").strip(),
        )
