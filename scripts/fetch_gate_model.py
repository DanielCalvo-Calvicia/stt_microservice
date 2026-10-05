r"""Makes sure the wake-phrase gate's model is downloaded. Run by the deployment tool after it writes the .env.

    windows\Scripts\python.exe scripts\fetch_gate_model.py

It reads the same settings as the service (STT_GATE_ENABLED, STT_GATE_MODEL), does nothing when the gate is off,
and otherwise loads the model once, which downloads it into faster-whisper's cache when it is not there yet.
Exit code 0 = the model is ready (or not needed), 1 = it could not be fetched (the service downloads it on its
first start instead, or fails to start the gate when there is no network).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from infrastructure.config.stt_config import SttConfig  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")  # like the service: a real environment variable wins over the file
    cfg = SttConfig.from_env()
    if not cfg.gate_enabled:
        print("STT_GATE_ENABLED is off: no gate model needed")
        return 0
    print(f"Loading the gate model {cfg.gate_model} (downloads it the first time)")
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415

        WhisperModel(cfg.gate_model, device="cpu", compute_type="int8")
    except Exception as error:  # no network, a mistyped model name, a full disk
        print(f"Could not load the gate model {cfg.gate_model}: {error}", file=sys.stderr)
        return 1
    print(f"Gate model {cfg.gate_model} is ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
