import pytest

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
    assert (cfg.gate_enabled, cfg.gate_model, cfg.gate_prompt) == (False, "base", "Oblivion 306.")


def test_gate_settings_are_read_from_the_environment():
    cfg = SttConfig.from_env({"STT_GATE_ENABLED": "TRUE", "STT_GATE_MODEL": " base.en ", "STT_GATE_PROMPT": "Robot 7"})
    assert (cfg.gate_enabled, cfg.gate_model, cfg.gate_prompt) == (True, "base.en", "Robot 7")
    assert SttConfig.from_env({"STT_GATE_ENABLED": "no"}).gate_enabled is False


def test_the_openai_prompt_is_empty_by_default_and_comes_from_the_environment():
    assert SttConfig.from_env({}).prompt == ""
    assert SttConfig.from_env({"STT_PROMPT": " Oblivion 306 "}).prompt == "Oblivion 306"


# --- the settings of the local models (T-01.2.2): model, threads, compute type ---


def test_local_model_settings_default_to_the_values_that_were_constants():
    cfg = SttConfig.from_env({})
    assert (cfg.model, cfg.threads, cfg.compute_type) == ("small.en", 2, "int8")


def test_local_model_settings_are_read_from_the_environment_trimmed_and_lower_cased():
    cfg = SttConfig.from_env(
        {"STT_MODEL": " small ", "STT_THREADS": " 4 ", "STT_COMPUTE_TYPE": " Int8_Float16 "}
    )
    assert (cfg.model, cfg.threads, cfg.compute_type) == ("small", 4, "int8_float16")


def test_a_multilingual_model_and_another_language_reach_the_config_unchanged():
    cfg = SttConfig.from_env({"STT_ENGINE": "local", "STT_MODEL": "small", "STT_LANGUAGE": "es"})
    assert (cfg.engine, cfg.model, cfg.language) == ("local", "small", "es")


def test_blank_local_model_settings_fall_back_to_the_defaults():
    cfg = SttConfig.from_env({"STT_MODEL": "  ", "STT_THREADS": "", "STT_COMPUTE_TYPE": "   "})
    assert (cfg.model, cfg.threads, cfg.compute_type) == ("small.en", 2, "int8")


def test_zero_threads_is_valid_and_means_let_ctranslate2_choose():
    assert SttConfig.from_env({"STT_THREADS": "0"}).threads == 0


@pytest.mark.parametrize("bad", ["many", "2.5", "-1", "1e2", "4 threads"])
def test_a_bad_thread_count_stops_the_start_with_an_error_that_names_the_variable(bad):
    with pytest.raises(ValueError) as raised:
        SttConfig.from_env({"STT_THREADS": bad})

    assert "STT_THREADS" in str(raised.value) and bad in str(raised.value)


def test_the_new_settings_do_not_change_the_existing_ones():
    cfg = SttConfig.from_env({"STT_MODEL": "base.en", "STT_GATE_MODEL": "tiny", "STT_PROMPT": "x"})
    assert (cfg.gate_model, cfg.prompt, cfg.engine, cfg.language) == ("tiny", "x", "openai", "en")
