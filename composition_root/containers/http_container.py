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


def new_http_container(server_cfg: ServerConfig, stt_cfg: SttConfig) -> HttpContainer:
    transcription = deps.new_transcription(stt_cfg)
    service = deps.new_stt_service(transcription, server_cfg.service_name)
    app = deps.new_http_app(service, server_cfg.service_name)
    return HttpContainer(app=app, stt=service)
