from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from config import APP_FONT_FAMILY, DOWNLOADS_DIR, THUMBNAIL_SIZE
from database.artist_repository import ArtistRepository
from database.song_repository import SongRepository
from models.song import Song
from services.song_service import SongService
from services.thumbnail_service import ThumbnailService
from utils.filename import build_song_name


class SongManagementView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        artist_repository: ArtistRepository,
        song_repository: SongRepository,
        song_service: SongService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.song_repository = song_repository
        self.song_service = song_service
        self.thumbnail_service = thumbnail_service
        self.song_entries: dict[int, ctk.CTkEntry] = {}
        self.thumbnail_labels: dict[str, ctk.CTkLabel] = {}
        self.thumbnail_images: dict[str, ImageTk.PhotoImage] = {}
        self.thumbnail_requests: set[str] = set()
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=4)
        self.default_thumbnail = self._make_default_thumbnail()
        self.editing_song_id: int | None = None
        self.font = ctk.CTkFont(family=APP_FONT_FAMILY, size=13)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.refresh_button = ctk.CTkButton(toolbar, text="重新整理", command=self.reload_songs, font=self.font)
        self.refresh_button.pack(side="left", padx=12, pady=10)
        self.status_label = ctk.CTkLabel(toolbar, text="", anchor="w", font=self.font)
        self.status_label.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        self.song_list = ctk.CTkScrollableFrame(self)
        self.song_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.song_list.grid_columnconfigure(0, weight=1)
        self.reload_songs()

    def reload_songs(self) -> None:
        for child in self.song_list.winfo_children():
            child.destroy()
        self.song_entries.clear()
        self.thumbnail_labels.clear()
        artist_names = {
            artist.artist_id.lower(): artist.channel_name
            for artist in self.artist_repository.list_artists()
        }
        songs = self.song_repository.list_songs()
        if not songs:
            ctk.CTkLabel(self.song_list, text="尚無已下載歌曲", anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            self.set_status("")
            return
        for row, song in enumerate(songs):
            self._render_song(row, song, artist_names)
        self.set_status(f"共 {len(songs)} 首下載紀錄。")

    def _render_song(self, row: int, song: Song, artist_names: dict[str, str]) -> None:
        frame = ctk.CTkFrame(self.song_list)
        frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        frame.grid_columnconfigure(2, weight=1)

        thumb_label = ctk.CTkLabel(frame, image=self.default_thumbnail, text="")
        thumb_label.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=10)
        self.thumbnail_labels[song.youtube_video_id] = thumb_label
        if song.youtube_video_id in self.thumbnail_images:
            thumb_label.configure(image=self.thumbnail_images[song.youtube_video_id])
        else:
            self._load_song_thumbnail_async(song)

        status = self._song_status(song)
        artist_name = artist_names.get(song.artist_id.lower(), song.artist_id)
        ctk.CTkLabel(frame, text=artist_name, width=140, anchor="w", font=self.font).grid(
            row=0, column=1, sticky="nw", padx=(6, 6), pady=10
        )

        if self.editing_song_id == song.id:
            entry = ctk.CTkEntry(frame, font=self.font)
            entry.insert(0, self._display_song_name(song))
            entry.grid(row=0, column=2, sticky="ew", padx=6, pady=(10, 4))
            if song.id is not None:
                self.song_entries[song.id] = entry
            ctk.CTkButton(
                frame,
                text="儲存",
                width=72,
                command=lambda song_id=song.id: self.rename_song(song_id),
                font=self.font,
            ).grid(row=0, column=3, padx=4, pady=10)
            ctk.CTkButton(
                frame,
                text="取消",
                width=72,
                command=self.cancel_edit,
                font=self.font,
            ).grid(row=0, column=4, padx=(4, 10), pady=10)
        else:
            ctk.CTkLabel(frame, text=self._display_song_name(song), anchor="w", font=self.font).grid(
                row=0, column=2, sticky="ew", padx=6, pady=(10, 4)
            )
            ctk.CTkButton(
                frame,
                text="編輯",
                width=72,
                command=lambda song_id=song.id: self.start_edit(song_id),
                font=self.font,
            ).grid(row=0, column=3, padx=(6, 10), pady=10)

        detail = (
            f"原始標題：{song.original_title}\n"
            f"檔案：{self._display_file_path(song.file_path)}\n"
            f"狀態：{status}"
        )
        ctk.CTkLabel(frame, text=detail, anchor="w", justify="left", wraplength=760, font=self.font).grid(
            row=1, column=2, columnspan=3, sticky="ew", padx=6, pady=(0, 10)
        )

    def _load_song_thumbnail_async(self, song: Song) -> None:
        if song.youtube_video_id in self.thumbnail_requests:
            return
        self.thumbnail_requests.add(song.youtube_video_id)
        future = self.thumbnail_executor.submit(
            self.thumbnail_service.get_thumbnail, song.youtube_video_id, song.thumbnail_url
        )
        future.add_done_callback(
            lambda done, video_id=song.youtube_video_id: self.after(
                0, self._handle_thumbnail_loaded, video_id, done
            )
        )

    def _handle_thumbnail_loaded(self, video_id: str, future) -> None:
        label = self.thumbnail_labels.get(video_id)
        if label is None:
            return
        try:
            image = future.result()
        except Exception:
            image = None
        if image is None:
            return
        photo = ImageTk.PhotoImage(image)
        self.thumbnail_images[video_id] = photo
        label.configure(image=photo)

    def start_edit(self, song_id: int | None) -> None:
        self.editing_song_id = song_id
        self.reload_songs()

    def cancel_edit(self) -> None:
        self.editing_song_id = None
        self.reload_songs()

    def rename_song(self, song_id: int | None) -> None:
        if song_id is None:
            self.set_status("找不到歌曲 ID。", error=True)
            return
        entry = self.song_entries.get(song_id)
        if entry is None:
            self.set_status("找不到歌曲輸入框。", error=True)
            return
        try:
            song = self.song_service.rename_song(song_id, entry.get())
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.editing_song_id = None
        self.set_status(f"已改名：{song.file_name}")
        self.reload_songs()

    def _song_status(self, song: Song) -> str:
        if song.download_status == "downloaded" and not Path(song.file_path).exists():
            return "檔案遺失"
        return song.download_status

    def _display_song_name(self, song: Song) -> str:
        return build_song_name(song.artist_id, song.song_name)

    def _display_file_path(self, file_path: str) -> str:
        path = Path(file_path)
        try:
            return str(path.relative_to(DOWNLOADS_DIR.parent))
        except ValueError:
            parts = path.parts
            if "downloads" in parts:
                index = parts.index("downloads")
                return str(Path(*parts[index:]))
            return path.name

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def _make_default_thumbnail(self):
        image = Image.new("RGB", THUMBNAIL_SIZE, "#d9dee8")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, THUMBNAIL_SIZE[0] - 1, THUMBNAIL_SIZE[1] - 1), outline="#8d96a8")
        draw.text((44, 36), "No Image", fill="#4a5568")
        return ImageTk.PhotoImage(image)

    def destroy(self) -> None:
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
