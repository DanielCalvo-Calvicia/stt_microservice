from dataclasses import dataclass

from fastapi import FastAPI

from application.ports.inbound.stt_transcription_port import SttTranscriptionPort
from composition_root.dependencies import stt_dependencies as deps
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stt_config import SttConfig


@dataclass(slots=True, frozen=True)
class HttpContainer:
    app: FastAPI
    stt: SttTranscriptionPort  # kept so main_flow can stop the shared stream on shutdown
    gate: SttTranscriptionPort | None = None  # the wake-phrase gate's own shared stream, when enabled


def new_http_container(server_cfg: ServerConfig, stt_cfg: SttConfig) -> HttpContainer:
    transcription = deps.new_transcription(stt_cfg)
    service = deps.new_stt_service(transcription, server_cfg.service_name)
    gate = (
        deps.new_stt_service(deps.new_gate_transcription(stt_cfg), f"{server_cfg.service_name} gate", with_audio=True)
        if stt_cfg.gate_enabled
        else None
    )
    app = deps.new_http_app(service, server_cfg.service_name, gate)
    return HttpContainer(app=app, stt=service, gate=gate)
