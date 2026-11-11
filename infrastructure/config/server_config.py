import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ServerConfig:
    service_name: str
    host: str
    port: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "ServerConfig":
        return cls(
            service_name=env.get("SERVICE_NAME", "STT Microservice"),
            host=env.get("SERVICE_HOST", "127.0.0.1"),
            port=int(env.get("SERVICE_PORT", "8001")),
        )
