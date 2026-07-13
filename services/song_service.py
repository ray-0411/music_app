from pathlib import Path

from database.song_repository import SongRepository
from models.song import Song
from utils.filename import build_mp3_filename, sanitize_filename_stem


class SongService:
    def __init__(self, song_repository: SongRepository | None = None) -> None:
        self.song_repository = song_repository or SongRepository()

    def rename_song(self, song_id: int, new_song_name: str) -> Song:
        display_name = sanitize_filename_stem(new_song_name)
        if not new_song_name.strip() or display_name == "untitled":
            raise ValueError("歌曲名稱不能空白。")

        song = self.song_repository.get_by_id(song_id)
        if song is None:
            raise ValueError("找不到歌曲。")
        if display_name == sanitize_filename_stem(song.song_name):
            return song

        old_path = Path(song.file_path)
        if not old_path.exists():
            raise ValueError("找不到原本的 MP3 檔案，無法改名。")

        new_file_name = build_mp3_filename(song.artist_id, display_name)
        new_path = old_path.with_name(new_file_name)
        if new_path != old_path and new_path.exists():
            raise ValueError("同資料夾已有相同檔名，請換一個歌曲名稱。")

        if new_path != old_path:
            old_path.rename(new_path)

        try:
            return self.song_repository.update_song_file_info(
                song_id,
                song_name=display_name,
                file_name=new_file_name,
                file_path=new_path,
            )
        except Exception:
            if new_path != old_path and new_path.exists() and not old_path.exists():
                new_path.rename(old_path)
            raise
