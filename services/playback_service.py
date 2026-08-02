from pathlib import Path
import random
from dataclasses import replace

from database.rating_repository import RatingRepository
from models.song import Song
from services.settings_service import SettingsService

try:
    import vlc
except Exception:  # pragma: no cover - depends on local VLC installation
    vlc = None


class PlaybackService:
    def __init__(
        self,
        settings_service: SettingsService | None = None,
        rating_repository: RatingRepository | None = None,
    ) -> None:
        self.settings_service = settings_service or SettingsService()
        self.rating_repository = rating_repository or RatingRepository()
        self.songs: list[Song] = []
        self.current_index = 0
        self.preview_next_index: int | None = None
        self.forced_next_index: int | None = None
        self.suppress_previous_display = False
        self.play_history_indices: list[int] = []
        self.play_history_ids: list[int] = []
        self.instance = None
        self.player = None
        self.volume = self.settings_service.get_volume()
        self.available = vlc is not None
        if self.available:
            try:
                self.instance = vlc.Instance()
                self.player = self.instance.media_player_new()
            except Exception:
                self.available = False

    def load_playlist(self, songs: list[Song]) -> None:
        current_song = self.current_song()
        current_song_id = current_song.id if current_song else None
        self.songs = [song for song in songs if Path(song.file_path).exists()]
        if current_song_id is not None:
            matched_index = next(
                (index for index, song in enumerate(self.songs) if song.id == current_song_id),
                None,
            )
            if matched_index is not None:
                self.current_index = matched_index
        if self.current_index >= len(self.songs):
            self.current_index = 0
            self.preview_next_index = None
            self.forced_next_index = None
            self.suppress_previous_display = False
            self.play_history_indices.clear()
            self.play_history_ids.clear()
        if self.songs:
            self._remember_current_song()

    def current_song(self) -> Song | None:
        if not self.songs:
            return None
        return self.songs[self.current_index]

    def previous_song(self) -> Song | None:
        if not self.songs:
            return None
        if self.suppress_previous_display:
            return None
        if len(self.play_history_indices) >= 2:
            return self.songs[self.play_history_indices[-2]]
        index = self.current_index - 1
        if index < 0:
            return None
        return self.songs[index]

    def next_song(self) -> Song | None:
        if not self.songs:
            return None
        if self.forced_next_index is not None and 0 <= self.forced_next_index < len(self.songs):
            return self.songs[self.forced_next_index]
        if self.get_play_order() == "random":
            index = self._preview_random_next_index()
            return self.songs[index] if index is not None else None
        index = self.current_index + 1
        if index >= len(self.songs):
            return None
        return self.songs[index]

    def play_current(self) -> None:
        self._require_player()
        song = self.current_song()
        if song is None:
            raise ValueError("沒有可播放的歌曲。")
        media = self.instance.media_new_path(str(Path(song.file_path)))
        self.player.set_media(media)
        self._apply_effective_volume(song)
        self.player.play()
        self._remember_current_song()

    def load_current_paused(self) -> None:
        self._require_player()
        song = self.current_song()
        if song is None:
            raise ValueError("沒有可播放的歌曲。")
        media = self.instance.media_new_path(str(Path(song.file_path)))
        self.player.set_media(media)
        self._apply_effective_volume(song)
        self.player.stop()
        self._remember_current_song()

    def toggle_play_pause(self) -> bool:
        self._require_player()
        if self.current_song() is None:
            raise ValueError("沒有可播放的歌曲。")
        if self.player.get_media() is None:
            self.play_current()
            return True
        if self.player.is_playing():
            self.player.pause()
            return False
        self.player.play()
        return True

    def play_next(self, *, autoplay: bool = True) -> bool:
        next_index = self._next_index()
        if next_index is None:
            return False
        self.current_index = next_index
        self.forced_next_index = None
        self.suppress_previous_display = False
        if autoplay:
            self.play_current()
        else:
            self.load_current_paused()
        return True

    def play_previous(self, *, autoplay: bool = True) -> bool:
        previous_index = self._previous_index()
        if previous_index is None:
            return False
        old_current_index = self.current_index
        self.current_index = previous_index
        self.forced_next_index = old_current_index
        self.preview_next_index = None
        self.suppress_previous_display = True
        if self.play_history_indices and self.play_history_indices[-1] == old_current_index:
            self.play_history_indices.pop()
        if autoplay:
            self.play_current()
        else:
            self.load_current_paused()
        return True

    def set_forced_next_song(self, song_id: int) -> bool:
        if not self.songs:
            return False
        current_song = self.current_song()
        if current_song is not None and current_song.id == song_id:
            return False
        matched_index = next(
            (index for index, song in enumerate(self.songs) if song.id == song_id),
            None,
        )
        if matched_index is None:
            return False
        self.forced_next_index = matched_index
        self.preview_next_index = None
        return True

    def restart_with_current_settings(self, *, autoplay: bool = False) -> bool:
        if not self.songs:
            return False
        self.play_history_ids.clear()
        self.play_history_indices.clear()
        self.preview_next_index = None
        self.forced_next_index = None
        self.suppress_previous_display = False
        if self.get_play_order() == "random":
            indices = list(range(len(self.songs)))
            self.current_index = self._weighted_random_index(indices) if self.get_random_mode() == "rating" else random.choice(indices)
        else:
            self.current_index = 0
        if autoplay:
            self.play_current()
        else:
            self.load_current_paused()
        self.suppress_previous_display = True
        self.preview_next_index = None
        if self.get_play_order() == "random":
            self._preview_random_next_index()
        return True

    def stop(self) -> None:
        if self.player is not None:
            self.player.stop()

    def is_playing(self) -> bool:
        return bool(self.player and self.player.is_playing())

    def is_ended(self) -> bool:
        if vlc is None or self.player is None:
            return False
        return self.player.get_state() == vlc.State.Ended

    def get_time_ms(self) -> int:
        if self.player is None:
            return 0
        time_ms = self.player.get_time()
        return max(time_ms, 0)

    def get_length_ms(self) -> int:
        if self.player is None:
            return 0
        length_ms = self.player.get_length()
        return max(length_ms, 0)

    def seek_ms(self, time_ms: int) -> None:
        self._require_player()
        if self.player.get_media() is None:
            self.play_current()
        self.player.set_time(max(time_ms, 0))

    def set_volume(self, volume: int) -> None:
        self._require_player()
        self.volume = max(0, min(int(volume), 100))
        self._apply_effective_volume(self.current_song())
        self.settings_service.set_volume(self.volume)

    def get_volume(self) -> int:
        return self.volume

    def set_current_song_volume_percent(self, song_volume_percent: int) -> None:
        song = self.current_song()
        if song is None:
            return
        volume = max(0, min(int(song_volume_percent), 200))
        updated_song = replace(song, song_volume_percent=volume)
        self.songs[self.current_index] = updated_song
        self._apply_effective_volume(updated_song)

    def current_song_volume_percent(self) -> int:
        song = self.current_song()
        return song.song_volume_percent if song else 100

    def get_play_order(self) -> str:
        return self.settings_service.get_play_order()

    def set_play_order(self, play_order: str) -> None:
        self.settings_service.set_play_order(play_order)
        self.preview_next_index = None
        self.forced_next_index = None
        self.suppress_previous_display = False

    def get_random_mode(self) -> str:
        return self.settings_service.get_random_mode()

    def set_random_mode(self, random_mode: str) -> None:
        self.settings_service.set_random_mode(random_mode)
        self.preview_next_index = None
        self.forced_next_index = None

    def get_repeat_gap(self) -> int:
        return self.settings_service.get_repeat_gap()

    def set_repeat_gap(self, repeat_gap: int) -> None:
        self.settings_service.set_repeat_gap(repeat_gap)
        self.preview_next_index = None

    def save_playback_settings(
        self,
        *,
        play_order: str,
        random_mode: str,
        repeat_gap: int,
        reset_next: bool,
    ) -> None:
        self.settings_service.set_play_order(play_order)
        self.settings_service.set_random_mode(random_mode)
        self.settings_service.set_repeat_gap(repeat_gap)
        if reset_next:
            self.preview_next_index = None
            self.forced_next_index = None
            self.suppress_previous_display = False

    def _next_index(self) -> int | None:
        if not self.songs:
            return None
        if self.forced_next_index is not None and 0 <= self.forced_next_index < len(self.songs):
            return self.forced_next_index
        if self.get_play_order() == "random":
            index = self._preview_random_next_index()
            self.preview_next_index = None
            return index
        index = self.current_index + 1
        return index if index < len(self.songs) else None

    def _previous_index(self) -> int | None:
        if not self.songs:
            return None
        if len(self.play_history_indices) >= 2:
            return self.play_history_indices[-2]
        index = self.current_index - 1
        return index if index >= 0 else None

    def _choose_random_next_index(self) -> int | None:
        if not self.songs:
            return None
        candidates = self._random_candidate_indices()
        if not candidates:
            return None
        if self.get_random_mode() == "rating":
            return self._weighted_random_index(candidates)
        return random.choice(candidates)

    def _preview_random_next_index(self) -> int | None:
        if self.preview_next_index is not None and 0 <= self.preview_next_index < len(self.songs):
            return self.preview_next_index
        self.preview_next_index = self._choose_random_next_index()
        return self.preview_next_index

    def _random_candidate_indices(self) -> list[int]:
        recent_ids = set(self.play_history_ids[-self.get_repeat_gap() :])
        candidates = [
            index
            for index, song in enumerate(self.songs)
            if index != self.current_index and (song.id is None or song.id not in recent_ids)
        ]
        if candidates:
            return candidates
        fallback = [index for index in range(len(self.songs)) if index != self.current_index]
        return fallback or [self.current_index]

    def _weighted_random_index(self, candidates: list[int]) -> int:
        weights = []
        for index in candidates:
            song = self.songs[index]
            score = self._song_random_weight_score(song)
            weights.append(max(score, 0.1))
        return random.choices(candidates, weights=weights, k=1)[0]

    def _song_random_weight_score(self, song: Song) -> float:
        song_score = self.rating_repository.song_algorithm_score(song.id) if song.id is not None else 5.0
        artist_score = self.rating_repository.artist_algorithm_score(song.artist_id)
        random_bonus = random.uniform(1, 5)
        return song_score + (artist_score / 2) + random_bonus

    def _remember_current_song(self) -> None:
        song = self.current_song()
        if self.current_index < 0 or self.current_index >= len(self.songs):
            return
        added_history = False
        if not self.play_history_indices or self.play_history_indices[-1] != self.current_index:
            self.play_history_indices.append(self.current_index)
            added_history = True
        if song is None or song.id is None:
            return
        if added_history:
            self.play_history_ids.append(song.id)
        max_history = max(self.get_repeat_gap(), 1) * 3
        if len(self.play_history_ids) > max_history:
            self.play_history_ids = self.play_history_ids[-max_history:]
        if len(self.play_history_indices) > max_history:
            self.play_history_indices = self.play_history_indices[-max_history:]

    def _apply_effective_volume(self, song: Song | None) -> None:
        if self.player is None:
            return
        song_volume_percent = song.song_volume_percent if song else 100
        effective_volume = round(self.volume * song_volume_percent / 100)
        self.player.audio_set_volume(max(0, min(effective_volume, 200)))

    def _require_player(self) -> None:
        if not self.available or self.instance is None or self.player is None:
            raise RuntimeError("找不到可用的 VLC。請先安裝 VLC 桌面版與 python-vlc。")
