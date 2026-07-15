import json
from typing import Any

from config import SETTINGS_PATH


class SettingsService:
    def __init__(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.settings = self._load()

    def get_volume(self, default: int = 100) -> int:
        value = self.settings.get("volume", default)
        try:
            return max(0, min(int(value), 100))
        except (TypeError, ValueError):
            return default

    def set_volume(self, volume: int) -> None:
        self.settings["volume"] = max(0, min(int(volume), 100))
        self._save()

    def _load(self) -> dict[str, Any]:
        if not SETTINGS_PATH.exists():
            return {}
        try:
            with SETTINGS_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self) -> None:
        with SETTINGS_PATH.open("w", encoding="utf-8") as file:
            json.dump(self.settings, file, ensure_ascii=False, indent=2)
