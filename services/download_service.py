from collections.abc import Callable
from pathlib import Path

import yt_dlp

from config import DOWNLOADS_DIR, MP3_QUALITY_KBPS
from database.song_repository import SongRepository
from models.artist import Artist
from models.video import Video
from services.thumbnail_service import ThumbnailService
from utils.filename import build_mp3_filename, build_song_name


ProgressCallback = Callable[[str, str], None]


class DownloadService:
    def __init__(
        self,
        song_repository: SongRepository | None = None,
        thumbnail_service: ThumbnailService | None = None,
    ) -> None:
        self.song_repository = song_repository or SongRepository()
        self.thumbnail_service = thumbnail_service or ThumbnailService()

    def download_video(
        self, artist: Artist, video: Video, progress_callback: ProgressCallback
    ) -> bool:
        existing = self.song_repository.get_by_video_id(video.youtube_video_id)
        if existing and Path(existing.file_path).exists():
            progress_callback(video.youtube_video_id, "已下載，略過")
            return False

        artist_dir = DOWNLOADS_DIR / artist.artist_id
        artist_dir.mkdir(parents=True, exist_ok=True)
        file_name = build_mp3_filename(artist.artist_id, video.title)
        song_name = build_song_name(artist.artist_id, video.title)
        final_path = artist_dir / file_name
        temp_template = str(artist_dir / f"{Path(file_name).stem}.%(ext)s")

        def hook(status: dict) -> None:
            if status.get("status") == "downloading":
                percent = status.get("_percent_str", "").strip()
                progress_callback(video.youtube_video_id, f"下載中 {percent}".strip())
            elif status.get("status") == "finished":
                progress_callback(video.youtube_video_id, "轉換 MP3 中")

        options = {
            "format": "bestaudio/best",
            "outtmpl": temp_template,
            "quiet": True,
            "noplaylist": True,
            "progress_hooks": [hook],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": MP3_QUALITY_KBPS,
                }
            ],
        }
        try:
            progress_callback(video.youtube_video_id, "開始下載")
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([video.youtube_url])
            if not final_path.exists():
                candidates = list(artist_dir.glob(f"{Path(file_name).stem}*.mp3"))
                if candidates:
                    candidates[0].replace(final_path)
            if not final_path.exists():
                raise RuntimeError("下載完成後找不到 MP3 檔案。")
            self.thumbnail_service.get_thumbnail(video.youtube_video_id, video.thumbnail_url)
            self.thumbnail_service.get_channel_avatar(artist.channel_id, artist.avatar_url)
            self.song_repository.save_downloaded_song(
                artist_id=artist.artist_id,
                video=video,
                song_name=song_name,
                file_name=file_name,
                file_path=final_path,
            )
            progress_callback(video.youtube_video_id, "完成")
            return True
        except Exception as exc:
            progress_callback(video.youtube_video_id, f"失敗：{exc}")
            return False
