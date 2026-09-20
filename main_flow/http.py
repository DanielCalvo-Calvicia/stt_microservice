from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from shared_logging import get_logger, init_logging

from composition_root.containers.http_container import HttpContainer, new_http_container
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stt_config import SttConfig

logger = get_logger(__name__)

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


async def run_http() -> None:
    # VS Code debugpy with integratedTerminal does not always inject envFile variables,
    # so load the file explicitly before anything reads the environment.
    load_dotenv(dotenv_path=_ENV_FILE)
    server_cfg = ServerConfig.from_env()
    stt_cfg = SttConfig.from_env()
    init_logging("stt")

    container = new_http_container(server_cfg, stt_cfg)
    server = uvicorn.Server(
        uvicorn.Config(
            container.app,
            host=server_cfg.host,
            port=server_cfg.port,
            log_config=None,
            timeout_keep_alive=60,
        )
    )
    logger.info(
        "Starting server",
        service_name=server_cfg.service_name,
        host=server_cfg.host,
        port=server_cfg.port,
    )
    try:
        await server.serve()  # returns after SIGINT/SIGTERM
    finally:
        await _cleanup(container)


async def _cleanup(container: HttpContainer) -> None:
    logger.info("Server stopped; stopping the shared stream")
    try:
        await container.stt.stop_stream()
    except Exception:
        logger.exception("Failed to stop the shared stream during cleanup")
    logger.info("Cleanup finished")
