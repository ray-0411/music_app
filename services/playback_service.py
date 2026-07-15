from pathlib import Path

from models.song import Song
from services.settings_service import SettingsService

try:
    import vlc
except Exception:  # pragma: no cover - depends on local VLC installation
    vlc = None


class PlaybackService:
    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self.settings_service = settings_service or SettingsService()
        self.songs: list[Song] = []
        self.current_index = 0
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
        self.songs = [song for song in songs if Path(song.file_path).exists()]
        if self.current_index >= len(self.songs):
            self.current_index = 0

    def current_song(self) -> Song | None:
        if not self.songs:
            return None
        return self.songs[self.current_index]

    def previous_song(self) -> Song | None:
        if not self.songs:
            return None
        index = self.current_index - 1
        if index < 0:
            return None
        return self.songs[index]

    def next_song(self) -> Song | None:
        if not self.songs:
            return None
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
        self.player.audio_set_volume(self.volume)
        self.player.play()

    def load_current_paused(self) -> None:
        self._require_player()
        song = self.current_song()
        if song is None:
            raise ValueError("沒有可播放的歌曲。")
        media = self.instance.media_new_path(str(Path(song.file_path)))
        self.player.set_media(media)
        self.player.audio_set_volume(self.volume)
        self.player.stop()

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
        if self.next_song() is None:
            return False
        self.current_index += 1
        if autoplay:
            self.play_current()
        else:
            self.load_current_paused()
        return True

    def play_previous(self, *, autoplay: bool = True) -> bool:
        if self.previous_song() is None:
            return False
        self.current_index -= 1
        if autoplay:
            self.play_current()
        else:
            self.load_current_paused()
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
        self.player.audio_set_volume(self.volume)
        self.settings_service.set_volume(self.volume)

    def get_volume(self) -> int:
        return self.volume

    def _require_player(self) -> None:
        if not self.available or self.instance is None or self.player is None:
            raise RuntimeError("找不到可用的 VLC。請先安裝 VLC 桌面版與 python-vlc。")
