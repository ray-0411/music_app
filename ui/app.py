import customtkinter as ctk

from config import APP_FONT_FAMILY, CACHE_DIR, CHANNEL_AVATAR_CACHE_DIR, DOWNLOADS_DIR, THUMBNAIL_CACHE_DIR
from database.artist_repository import ArtistRepository
from database.song_repository import SongRepository
from services.download_service import DownloadService
from services.song_service import SongService
from services.thumbnail_service import ThumbnailService
from services.youtube_service import YouTubeService
from ui.artist_view import ArtistView
from ui.song_management_view import SongManagementView
from ui.video_view import VideoView


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YouTube Music Downloader")
        self.geometry("1120x760")
        self.minsize(980, 640)
        self.option_add("*Font", f"{{{APP_FONT_FAMILY}}} 10")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CHANNEL_AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.artist_repository = ArtistRepository()
        self.song_repository = SongRepository()
        self.youtube_service = YouTubeService()
        self.thumbnail_service = ThumbnailService()
        self.download_service = DownloadService(self.song_repository, self.thumbnail_service)
        self.song_service = SongService(self.song_repository)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.artist_tab = self.tabs.add("歌手管理")
        self.video_tab = self.tabs.add("影片下載")
        self.song_tab = self.tabs.add("歌曲管理")

        self.video_view = VideoView(
            self.video_tab,
            artist_repository=self.artist_repository,
            song_repository=self.song_repository,
            youtube_service=self.youtube_service,
            thumbnail_service=self.thumbnail_service,
            download_service=self.download_service,
            on_downloads_changed=lambda: self.song_management_view.reload_songs(),
        )
        self.video_view.pack(fill="both", expand=True)

        self.song_management_view = SongManagementView(
            self.song_tab,
            artist_repository=self.artist_repository,
            song_repository=self.song_repository,
            song_service=self.song_service,
            thumbnail_service=self.thumbnail_service,
        )
        self.song_management_view.pack(fill="both", expand=True)

        self.artist_view = ArtistView(
            self.artist_tab,
            artist_repository=self.artist_repository,
            youtube_service=self.youtube_service,
            thumbnail_service=self.thumbnail_service,
            on_artists_changed=self._artists_changed,
        )
        self.artist_view.pack(fill="both", expand=True)

    def _artists_changed(self) -> None:
        self.video_view.reload_artists()
