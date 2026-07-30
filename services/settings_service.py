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

    def get_play_order(self, default: str = "sequential") -> str:
        value = self.settings.get("play_order", default)
        return value if value in {"sequential", "random"} else default

    def set_play_order(self, play_order: str) -> None:
        if play_order not in {"sequential", "random"}:
            raise ValueError("播放順序設定不正確。")
        self.settings["play_order"] = play_order
        self._save()

    def get_random_mode(self, default: str = "equal") -> str:
        value = self.settings.get("random_mode", default)
        return value if value in {"equal", "rating"} else default

    def set_random_mode(self, random_mode: str) -> None:
        if random_mode not in {"equal", "rating"}:
            raise ValueError("隨機模式設定不正確。")
        self.settings["random_mode"] = random_mode
        self._save()

    def get_repeat_gap(self, default: int = 5) -> int:
        value = self.settings.get("repeat_gap", default)
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    def set_repeat_gap(self, repeat_gap: int) -> None:
        self.settings["repeat_gap"] = max(0, int(repeat_gap))
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
