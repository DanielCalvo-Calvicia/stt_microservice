from application.ports.outbound.stt_outbound_port import SttOutboundPort
from application.ports.service.stt_service_port import SttServicePort
from application.services.stt_service import SttService


def new_stt_service(transcription: SttOutboundPort, name: str, *, with_audio: bool = False) -> SttServicePort:
    return SttService(transcription=transcription, name=name, with_audio=with_audio)
