from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "ui": {"language": "en"},
    "local_stt": {"language": "auto"},
    "llm": {
        "provider": "openai_compatible",
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key": "",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
        "timeout_seconds": 60,
        "use_response_format": True,
    },
    "stt": {
        "provider": "openai_compatible",
        "mode": "non_realtime",
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key": "",
        "api_key_env": "OPENAI_API_KEY",
        "model": "whisper-1",
        "language": "zh",
        "timeout_seconds": 120,
        "realtime_url": "ws://127.0.0.1:8000/v1/audio/realtime",
    },
    "ai": {
        "default_target": "selected_date",
        "auto_apply_after_extract": False,
    },
}


def deep_merge(default: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(default)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class SettingsManager:
    def __init__(self, path: Path):
        self.path = path
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            loaded = {}
        self.settings = deep_merge(DEFAULT_SETTINGS, loaded)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, section: str) -> dict[str, Any]:
        return self.settings.setdefault(section, copy.deepcopy(DEFAULT_SETTINGS.get(section, {})))

    def update_section(self, section: str, values: dict[str, Any]) -> None:
        current = self.get(section)
        current.update(values)
        self.save()

    def resolved_api_key(self, section: str) -> str:
        data = self.get(section)
        direct = str(data.get("api_key", "")).strip()
        if direct:
            return direct
        env_name = str(data.get("api_key_env", "")).strip()
        if env_name:
            return os.environ.get(env_name, "").strip()
        return ""
