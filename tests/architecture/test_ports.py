"""Fitness function: the service and every adapter implement a port, and the ports are the contract.

    inbound adapter (SttHandler)  implements  SttInboundPort
    service (SttService)          implements  SttServicePort
    outbound adapter (engines)    implement   SttOutboundPort

A new inbound or outbound adapter implements the same port as the others, so its functions are the same.
"""

import ast
from pathlib import Path

import pytest

from application.ports.inbound.stt_inbound_port import SttInboundPort
from application.ports.outbound.stt_outbound_port import SttOutboundPort
from application.ports.service.stt_service_port import SttServicePort
from application.services.stt_service import SttService
from infrastructure.inbound.http.http_handler import SttHandler
from infrastructure.outbound.local_whisper.local_whisper_transcription import LocalWhisperTranscription
from infrastructure.outbound.openai_whisper.openai_whisper_transcription import OpenAIWhisperTranscription

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("component", "port"),
    [
        (SttService, SttServicePort),
        (SttHandler, SttInboundPort),
        (LocalWhisperTranscription, SttOutboundPort),
        (OpenAIWhisperTranscription, SttOutboundPort),
    ],
)
def test_each_component_implements_its_port(component, port):
    assert issubclass(component, port)
    assert not component.__abstractmethods__, "a port operation is not implemented"


@pytest.mark.parametrize(
    ("port", "operations"),
    [
        (SttInboundPort, {"health", "is_available", "stop", "process_stream", "set_stream", "get_stream", "process_batch"}),
        (SttServicePort, {"process_stream", "set_stream", "get_stream", "stop_stream", "process_batch", "is_available"}),
        (SttOutboundPort, {"transcribe_batch", "is_available"}),
    ],
)
def test_the_port_is_the_contract(port, operations):
    assert port.__abstractmethods__ == operations


def _classes(package: str, suffix: str) -> list[tuple[str, ast.ClassDef]]:
    found = []
    for path in sorted((ROOT / "infrastructure" / package).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef) and node.name.endswith(suffix):
                found.append((f"{path.relative_to(ROOT)}:{node.name}", node))
    return found


def _base_names(node: ast.ClassDef) -> set[str]:
    return {base.id for base in node.bases if isinstance(base, ast.Name)}


def test_every_inbound_adapter_implements_the_inbound_port():
    adapters = _classes("inbound", "Handler")
    assert adapters, "no inbound adapter found"
    missing = [name for name, node in adapters if "SttInboundPort" not in _base_names(node)]
    assert not missing, f"inbound adapters that do not implement SttInboundPort: {missing}"


def test_every_outbound_adapter_implements_the_outbound_port():
    adapters = _classes("outbound", "Transcription")
    assert adapters, "no outbound adapter found"
    missing = [name for name, node in adapters if "SttOutboundPort" not in _base_names(node)]
    assert not missing, f"outbound adapters that do not implement SttOutboundPort: {missing}"
