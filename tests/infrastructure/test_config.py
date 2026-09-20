from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stt_config import SttConfig


def test_server_config_defaults():
    cfg = ServerConfig.from_env({})
    assert (cfg.service_name, cfg.host, cfg.port) == (
        "STT Microservice",
        "127.0.0.1",
        8001,
    )


def test_server_config_overrides():
    cfg = ServerConfig.from_env(
        {
            "SERVICE_NAME": "X",
            "SERVICE_HOST": "0.0.0.0",
            "SERVICE_PORT": "9000",
        }
    )
    assert (cfg.service_name, cfg.host, cfg.port) == ("X", "0.0.0.0", 9000)


def test_stt_config_defaults():
    assert SttConfig.from_env({}) == SttConfig("openai", "en", "")


def test_stt_config_normalises_values():
    cfg = SttConfig.from_env(
        {
            "STT_ENGINE": "LOCAL",
            "STT_LANGUAGE": "  es ",
            "OPENAI_API_KEY": "sk-test",
        }
    )
    assert cfg == SttConfig("local", "es", "sk-test")


def test_blank_language_falls_back():
    cfg = SttConfig.from_env({"STT_LANGUAGE": "   "})
    assert cfg.language == "en"
