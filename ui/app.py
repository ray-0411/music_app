import customtkinter as ctk

from config import APP_FONT_FAMILY, ARTIST_IMAGE_DIR, ASSETS_DIR, CACHE_DIR, DOWNLOADS_DIR, SONG_IMAGE_DIR, THUMBNAIL_CACHE_DIR
from database.artist_repository import ArtistRepository
from database.song_repository import SongRepository
from database.tag_repository import TagRepository
from services.download_service import DownloadService
from services.song_service import SongService
from services.thumbnail_service import ThumbnailService
from services.youtube_service import YouTubeService
from ui.artist_view import ArtistView
from ui.fonts import base_font, button_font, title_font
from ui.song_management_view import SongManagementView
from ui.tag_management_view import TagManagementView
from ui.video_view import VideoView


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YouTube Music Downloader")
        self.minsize(980, 640)
        self.geometry("1120x760")
        self.option_add("*Font", f"{{{APP_FONT_FAMILY}}} 10")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        ARTIST_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        SONG_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.artist_repository = ArtistRepository()
        self.song_repository = SongRepository()
        self.tag_repository = TagRepository("artist")
        self.song_tag_repository = TagRepository("song")
        self.youtube_service = YouTubeService()
        self.thumbnail_service = ThumbnailService()
        self.download_service = DownloadService(self.song_repository, self.thumbnail_service)
        self.song_service = SongService(self.song_repository)

        self.font = base_font()
        self.nav_font = button_font()
        self.subnav_font = button_font()
        self.title_font = title_font()
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.subnav_buttons: list[ctk.CTkButton] = []
        self.current_section = ""

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=168, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="Music App",
            font=self.title_font,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(18, 16))

        self.content_shell = ctk.CTkFrame(self, fg_color="transparent")
        self.content_shell.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.content_shell.grid_columnconfigure(0, weight=1)
        self.content_shell.grid_rowconfigure(1, weight=1)

        self.subnav_frame = ctk.CTkFrame(self.content_shell)
        self.subnav_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.body_frame = ctk.CTkFrame(self.content_shell, fg_color="transparent")
        self.body_frame.grid(row=1, column=0, sticky="nsew")
        self.body_frame.grid_columnconfigure(0, weight=1)
        self.body_frame.grid_rowconfigure(0, weight=1)

        self.video_view = VideoView(
            self.body_frame,
            artist_repository=self.artist_repository,
            song_repository=self.song_repository,
            youtube_service=self.youtube_service,
            thumbnail_service=self.thumbnail_service,
            download_service=self.download_service,
            on_downloads_changed=lambda: self.song_management_view.reload_songs(),
        )
        self.video_view.grid(row=0, column=0, sticky="nsew")

        self.song_management_view = SongManagementView(
            self.body_frame,
            artist_repository=self.artist_repository,
            song_repository=self.song_repository,
            song_service=self.song_service,
            thumbnail_service=self.thumbnail_service,
            tag_repository=self.song_tag_repository,
        )
        self.song_management_view.grid(row=0, column=0, sticky="nsew")

        self.artist_view = ArtistView(
            self.body_frame,
            artist_repository=self.artist_repository,
            youtube_service=self.youtube_service,
            thumbnail_service=self.thumbnail_service,
            tag_repository=self.tag_repository,
            on_artists_changed=self._artists_changed,
        )
        self.artist_view.grid(row=0, column=0, sticky="nsew")

        self.player_placeholder = self._build_placeholder(
            "音樂播放器",
            "播放器功能預留中。之後可以放播放清單、隨機播放、播放控制列。",
        )
        self.download_single_placeholder = self._build_placeholder(
            "單曲下載",
            "單曲下載功能預留中。現在請先使用「頻道下載」。",
        )
        self.artist_tag_management_view = TagManagementView(
            self.body_frame,
            tag_repository=self.tag_repository,
        )
        self.artist_tag_management_view.grid(row=0, column=0, sticky="nsew")
        self.song_tag_management_view = TagManagementView(
            self.body_frame,
            tag_repository=self.song_tag_repository,
        )
        self.song_tag_management_view.grid(row=0, column=0, sticky="nsew")

        self.pages = {
            "player": self.player_placeholder,
            "artists": self.artist_view,
            "songs": self.song_management_view,
            "download_channel": self.video_view,
            "download_single": self.download_single_placeholder,
            "artist_tags": self.artist_tag_management_view,
            "song_tags": self.song_tag_management_view,
        }
        for page in self.pages.values():
            page.grid_remove()

        self.sections = {
            "player": {
                "label": "音樂播放器",
                "subnav": [("播放區", "player")],
            },
            "artists": {
                "label": "歌手管理",
                "subnav": [("歌手清單", "artists:list"), ("新增歌手", "artists:add")],
            },
            "songs": {
                "label": "歌曲管理",
                "subnav": [("歌曲清單", "songs"), ("修改歌曲", "songs")],
            },
            "tags": {
                "label": "標籤管理",
                "subnav": [("歌手標籤", "artist_tags"), ("歌曲標籤", "song_tags")],
            },
            "download": {
                "label": "下載歌曲",
                "subnav": [("頻道下載", "download_channel"), ("單曲下載", "download_single")],
            },
        }
        self._build_sidebar()
        self.show_section("player")
        self.after(100, self._maximize_window)

    def _artists_changed(self) -> None:
        self.video_view.reload_artists()

    def _build_sidebar(self) -> None:
        for section_key, section in self.sections.items():
            button = ctk.CTkButton(
                self.sidebar,
                text=section["label"],
                anchor="w",
                height=48,
                font=self.nav_font,
                command=lambda key=section_key: self.show_section(key),
            )
            button.pack(fill="x", padx=10, pady=5)
            self.nav_buttons[section_key] = button

    def show_section(self, section_key: str) -> None:
        self.current_section = section_key
        for key, button in self.nav_buttons.items():
            if key == section_key:
                button.configure(fg_color=("#3b8ed0", "#1f6aa5"))
            else:
                button.configure(fg_color=("gray75", "gray25"))
        self._build_subnav(section_key)
        first_page = self.sections[section_key]["subnav"][0][1]
        self.show_page(first_page)

    def _build_subnav(self, section_key: str) -> None:
        for child in self.subnav_frame.winfo_children():
            child.destroy()
        self.subnav_buttons.clear()
        title = ctk.CTkLabel(
            self.subnav_frame,
            text=self.sections[section_key]["label"],
            font=self.title_font,
        )
        title.pack(side="left", padx=(12, 16), pady=10)
        for label, page_key in self.sections[section_key]["subnav"]:
            button = ctk.CTkButton(
                self.subnav_frame,
                text=label,
                width=136,
                height=38,
                font=self.subnav_font,
                command=lambda key=page_key: self.show_page(key),
            )
            button.pack(side="left", padx=4, pady=10)
            self.subnav_buttons.append(button)

    def show_page(self, page_key: str) -> None:
        if page_key.startswith("artists:"):
            self.artist_view.show_add_page() if page_key.endswith(":add") else self.artist_view.show_list_page()
            page_key = "artists"
        for key, page in self.pages.items():
            if key == page_key:
                page.grid()
            else:
                page.grid_remove()

    def _build_placeholder(self, title: str, message: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.body_frame)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=title, font=self.title_font, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(18, 8)
        )
        ctk.CTkLabel(frame, text=message, font=self.font, anchor="nw", justify="left").grid(
            row=1, column=0, sticky="nsew", padx=18, pady=8
        )
        return frame

    def _maximize_window(self) -> None:
        try:
            self.state("zoomed")
        except Exception:
            width = self.winfo_screenwidth()
            height = self.winfo_screenheight()
            self.geometry(f"{width}x{height}+0+0")
