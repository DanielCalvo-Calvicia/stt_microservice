r"""Makes sure the local models the settings need are downloaded. Run by the deployment tool after it writes the .env.

    windows\Scripts\python.exe scripts\fetch_gate_model.py

It reads the same settings as the service (the environment, then the .env next to main.py) and loads, once each,
with the service's own threads and compute type, the models the service would load at start-up:

  * the main model (STT_MODEL) when STT_ENGINE is not "openai";
  * the wake-phrase gate's model (STT_GATE_MODEL) when STT_GATE_ENABLED is on.

Loading a model downloads it into faster-whisper's cache when it is not there yet. A model that fails to load
does not stop the others. Exit code 0 = every needed model is ready (or none is needed), 1 = at least one could
not be fetched (the service then downloads it on its first start instead, or fails to start without network).

A Docker build has neither the environment nor the .env, so there it needs nothing and fetches nothing: the
models have to be fetched at run time (ADR-009). The file keeps its first name because the deployment tool's
catalogue (config/catalogue.toml, another repository) names it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from infrastructure.config.stt_config import SttConfig  # noqa: E402


def _needed_models(cfg: SttConfig) -> list[tuple[str, str]]:
    """The ``(role, model name)`` pairs to load, main first; a name needed twice is listed once."""
    models: list[tuple[str, str]] = []
    if cfg.engine != "openai":
        models.append(("main", cfg.model))
    if cfg.gate_enabled:
        if models and models[0][1] == cfg.gate_model:
            models[0] = ("main and gate", cfg.model)
        else:
            models.append(("gate", cfg.gate_model))
    return models


def main() -> int:
    load_dotenv(ROOT / ".env")  # like the service: a real environment variable wins over the file
    try:
        cfg = SttConfig.from_env()
    except ValueError as error:  # a bad STT_THREADS: the service would not start either
        print(f"Invalid settings: {error}", file=sys.stderr)
        return 1
    models = _needed_models(cfg)
    if not models:
        print("No local model needed: STT_ENGINE is openai and STT_GATE_ENABLED is off")
        return 0
    failed = 0
    for role, model in models:
        print(f"Loading the {role} model {model} (downloads it the first time)")
        try:
            from faster_whisper import WhisperModel  # noqa: PLC0415

            WhisperModel(
                model, device="cpu", compute_type=cfg.compute_type, cpu_threads=cfg.threads
            )
        except Exception as error:  # no network, a mistyped model name, a full disk
            print(f"Could not load the {role} model {model}: {error}", file=sys.stderr)
            failed += 1
            continue
        print(f"{role.capitalize()} model {model} is ready")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
