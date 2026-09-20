import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SttConfig:
    engine: str
    language: str
    openai_api_key: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "SttConfig":
        return cls(
            engine=env.get("STT_ENGINE", "openai").lower(),
            language=env.get("STT_LANGUAGE", "en").strip() or "en",
            openai_api_key=env.get("OPENAI_API_KEY", ""),
        )
