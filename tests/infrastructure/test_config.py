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


def test_gate_settings_default_to_off_with_the_tiny_model_and_the_phrase_as_prompt():
    cfg = SttConfig.from_env({})
    assert (cfg.gate_enabled, cfg.gate_model, cfg.gate_prompt) == (False, "tiny.en", "Oblivion 306")


def test_gate_settings_are_read_from_the_environment():
    cfg = SttConfig.from_env({"STT_GATE_ENABLED": "TRUE", "STT_GATE_MODEL": " base.en ", "STT_GATE_PROMPT": "Robot 7"})
    assert (cfg.gate_enabled, cfg.gate_model, cfg.gate_prompt) == (True, "base.en", "Robot 7")
    assert SttConfig.from_env({"STT_GATE_ENABLED": "no"}).gate_enabled is False


def test_the_openai_prompt_is_empty_by_default_and_comes_from_the_environment():
    assert SttConfig.from_env({}).prompt == ""
    assert SttConfig.from_env({"STT_PROMPT": " Oblivion 306 "}).prompt == "Oblivion 306"
