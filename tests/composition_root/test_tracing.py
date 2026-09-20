from fastapi.testclient import TestClient
from shared_logging.testing import capture

from composition_root.containers import http_container
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stt_config import SttConfig

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"


def _client():
    container = http_container.new_http_container(
        ServerConfig.from_env({}), SttConfig.from_env({"OPENAI_API_KEY": "sk-test"})
    )
    return TestClient(container.app)


def test_incoming_trace_is_continued_and_logged_with_the_service_name():
    client = _client()

    with capture("stt") as logs:
        response = client.get("/health", headers={"traceparent": TRACEPARENT})

    assert response.status_code == 200
    assert response.headers["x-trace-id"] == TRACE_ID
    request_logs = [r for r in logs.records if r["logger"] == "shared_logging.http"]
    assert request_logs and {r["trace_id"] for r in request_logs} == {TRACE_ID}
    assert {r["service"] for r in logs.records} == {"stt"}


def test_request_without_a_trace_starts_a_new_one():
    client = _client()

    with capture("stt"):
        response = client.get("/health")

    assert len(response.headers["x-trace-id"]) == 32
