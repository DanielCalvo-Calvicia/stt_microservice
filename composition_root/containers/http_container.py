from dataclasses import dataclass

from fastapi import FastAPI

from application.ports.service.stt_service_port import SttServicePort
from composition_root.dependencies.gate_transcription_dependency import new_gate_transcription
from composition_root.dependencies.http_app_dependency import new_http_app
from composition_root.dependencies.stt_service_dependency import new_stt_service
from composition_root.dependencies.transcription_dependency import new_transcription
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stt_config import SttConfig


@dataclass(slots=True, frozen=True)
class HttpContainer:
    app: FastAPI
    stt: SttServicePort  # kept so main_flow can stop the shared stream on shutdown
    gate: SttServicePort | None = None  # the wake-phrase gate's own shared stream, when enabled


def new_http_container(server_cfg: ServerConfig, stt_cfg: SttConfig) -> HttpContainer:
    transcription = new_transcription(stt_cfg)
    service = new_stt_service(transcription, server_cfg.service_name)
    gate = (
        new_stt_service(new_gate_transcription(stt_cfg), f"{server_cfg.service_name} gate", with_audio=True)
        if stt_cfg.gate_enabled
        else None
    )
    app = new_http_app(service, server_cfg.service_name, gate)
    return HttpContainer(app=app, stt=service, gate=gate)
