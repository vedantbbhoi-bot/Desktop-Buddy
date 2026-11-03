"""src/config.py — loads config.json, dataclasses, env overrides."""
import json
import logging
import os
import pathlib
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "config.json"
CONFIG_EXAMPLE = REPO_ROOT / "config.example.json"


@dataclass
class LLMConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5-coder:3b"
    timeout: int = 30


@dataclass
class TTSConfig:
    piper_binary: Optional[str] = None
    model_path: str = "models/piper/en_US-lessac-medium.onnx"
    fallback_rate: int = 175


@dataclass
class STTConfig:
    model_dir: str = "models/vosk/vosk-model-small-en-us-0.15"
    sample_rate: int = 16000


@dataclass
class WindowConfig:
    x: int = 100
    y: int = 100
    width: int = 200
    height: int = 200


@dataclass
class AppConfig:
    scale: float = 1.0
    theme: str = "default"
    sprite_dir: str = "assets/sprites/default"
    always_on_top: bool = True
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    window: WindowConfig = field(default_factory=WindowConfig)


def _nested_update(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _nested_update(result[k], v)
        else:
            result[k] = v
    return result


def _apply_env_overrides(raw: dict) -> dict:
    """Apply environment variable overrides (BUDDY_ prefix)."""
    mapping = {
        "BUDDY_LLM_MODEL": ("llm", "model"),
        "BUDDY_LLM_URL": ("llm", "base_url"),
        "BUDDY_SCALE": ("scale",),
        "BUDDY_THEME": ("theme",),
        "BUDDY_ALWAYS_ON_TOP": ("always_on_top",),
    }
    for env_key, path in mapping.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        if len(path) == 1:
            raw[path[0]] = val
        else:
            raw.setdefault(path[0], {})[path[1]] = val
    return raw


def _parse_raw(raw: dict) -> AppConfig:
    llm_raw = raw.get("llm", {})
    tts_raw = raw.get("tts", {})
    stt_raw = raw.get("stt", {})
    win_raw = raw.get("window", {})
    return AppConfig(
        scale=float(raw.get("scale", 1.0)),
        theme=str(raw.get("theme", "default")),
        sprite_dir=str(raw.get("sprite_dir", "assets/sprites/default")),
        always_on_top=bool(raw.get("always_on_top", True)),
        llm=LLMConfig(
            base_url=llm_raw.get("base_url", "http://127.0.0.1:11434"),
            model=llm_raw.get("model", "qwen2.5-coder:3b"),
            timeout=int(llm_raw.get("timeout", 30)),
        ),
        tts=TTSConfig(
            piper_binary=tts_raw.get("piper_binary"),
            model_path=tts_raw.get("model_path", "models/piper/en_US-lessac-medium.onnx"),
            fallback_rate=int(tts_raw.get("fallback_rate", 175)),
        ),
        stt=STTConfig(
            model_dir=stt_raw.get("model_dir", "models/vosk/vosk-model-small-en-us-0.15"),
            sample_rate=int(stt_raw.get("sample_rate", 16000)),
        ),
        window=WindowConfig(
            x=int(win_raw.get("x", 100)),
            y=int(win_raw.get("y", 100)),
            width=int(win_raw.get("width", 200)),
            height=int(win_raw.get("height", 200)),
        ),
    )


def load_config() -> AppConfig:
    """Load config.json, falling back to config.example.json defaults.

    Environment variables with the BUDDY_ prefix override any file value.
    """
    # Start from example defaults so all keys are present
    raw: dict = {}
    if CONFIG_EXAMPLE.exists():
        with open(CONFIG_EXAMPLE, encoding="utf-8") as f:
            raw = json.load(f)

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            user = json.load(f)
        raw = _nested_update(raw, user)
        log.info("Loaded config from %s", CONFIG_FILE)
    else:
        log.warning(
            "config.json not found — using defaults. "
            "Copy config.example.json to config.json to customise."
        )

    raw = _apply_env_overrides(raw)
    return _parse_raw(raw)


# Module-level singleton — imported by other modules as `from src.config import CONFIG`
CONFIG: AppConfig = load_config()


if __name__ == "__main__":
    import pprint

    cfg = load_config()
    pprint.pprint(cfg)

