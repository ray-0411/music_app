from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from config import THUMBNAIL_SIZE
from database.artist_repository import ArtistRepository
from database.song_repository import SongRepository
from models.artist import Artist
from models.song import Song
from services.download_service import DownloadService
from services.thumbnail_service import ThumbnailService
from services.youtube_service import SingleVideoInfo, YouTubeService
from ui.fonts import base_font, button_font, small_title_font


SINGLE_PREVIEW_SIZE = (320, 180)


class SingleDownloadView(ctk.CTkFrame):
    ARTIST_PLACEHOLDER = "請選擇歌手"
    NO_ARTIST_TEXT = "尚未新增歌手"

    def __init__(
        self,
        master,
        *,
        artist_repository: ArtistRepository,
        song_repository: SongRepository,
        youtube_service: YouTubeService,
        thumbnail_service: ThumbnailService,
        download_service: DownloadService,
        on_downloads_changed=None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.song_repository = song_repository
        self.youtube_service = youtube_service
        self.thumbnail_service = thumbnail_service
        self.download_service = download_service
        self.on_downloads_changed = on_downloads_changed
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.artists: list[Artist] = []
        self.video_info: SingleVideoInfo | None = None
        self.selected_artist: Artist | None = None
        self.existing_song: Song | None = None
        self.preview_image = self._make_default_thumbnail()
        self.is_destroyed = False

        self.font = base_font()
        self.button_font = button_font()
        self.title_font = small_title_font()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        form = ctk.CTkFrame(self)
        form.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="YouTube 網址", font=self.font).grid(
            row=0, column=0, sticky="w", padx=(12, 8), pady=12
        )
        self.url_entry = ctk.CTkEntry(form, font=self.font)
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=12)
        self.url_entry.bind("<Return>", lambda _event: self.inspect_video())
        self.inspect_button = ctk.CTkButton(
            form,
            text="解析",
            command=self.inspect_video,
            font=self.button_font,
            width=92,
        )
        self.inspect_button.grid(row=0, column=2, padx=(8, 12), pady=12)

        ctk.CTkLabel(form, text="歌手", font=self.font).grid(
            row=1, column=0, sticky="w", padx=(12, 8), pady=12
        )
        self.artist_menu = ctk.CTkOptionMenu(
            form,
            values=[self.NO_ARTIST_TEXT],
            command=self._artist_selected,
            font=self.font,
        )
        self.artist_menu.grid(row=1, column=1, sticky="ew", padx=8, pady=12)
        self.download_button = ctk.CTkButton(
            form,
            text="下載",
            command=self.download_video,
            font=self.button_font,
            width=92,
            state="disabled",
        )
        self.download_button.grid(row=1, column=2, padx=(8, 12), pady=12)

        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.info_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self.info_frame,
            text="影片資訊",
            font=self.title_font,
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 8))
        self.title_label = self._make_info_row("歌名", 1)
        self.channel_label = self._make_info_row("頻道", 2)
        self.match_label = self._make_info_row("歌手比對", 3)
        self.duration_label = self._make_info_row("長度", 4)
        self.thumbnail_label = ctk.CTkLabel(self.info_frame, image=self.preview_image, text="")
        self.thumbnail_label.grid(row=1, column=2, rowspan=4, sticky="ne", padx=12, pady=8)

        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        status_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(status_frame, text="狀態", font=self.font).grid(
            row=0, column=0, sticky="w", padx=(12, 8), pady=10
        )
        self.status_label = ctk.CTkLabel(status_frame, text="", anchor="w", font=self.font)
        self.status_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=10)

        self.reload_artists()

    def _make_info_row(self, label: str, row: int) -> ctk.CTkLabel:
        ctk.CTkLabel(self.info_frame, text=label, font=self.font, anchor="w").grid(
            row=row,
            column=0,
            sticky="nw",
            padx=12,
            pady=8,
        )
        value = ctk.CTkLabel(
            self.info_frame,
            text="-",
            font=self.font,
            anchor="w",
            justify="left",
            wraplength=640,
        )
        value.grid(row=row, column=1, sticky="ew", padx=12, pady=8)
        return value

    def reload_artists(self) -> None:
        self.artists = self.artist_repository.list_artists()
        labels = [self._artist_label(artist) for artist in self.artists]
        if not labels:
            self.artist_menu.configure(values=[self.NO_ARTIST_TEXT])
            self.artist_menu.set(self.NO_ARTIST_TEXT)
            self.selected_artist = None
            self.download_button.configure(state="disabled")
            return
        self.artist_menu.configure(values=[self.ARTIST_PLACEHOLDER, *labels])
        if self.selected_artist and self._find_artist_by_id(self.selected_artist.artist_id):
            self.artist_menu.set(self._artist_label(self.selected_artist))
        else:
            self.selected_artist = None
            self.artist_menu.set(self.ARTIST_PLACEHOLDER)
            self.download_button.configure(state="disabled")

    def inspect_video(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            self.set_status("請輸入 YouTube 影片網址。", error=True)
            return
        self.url_entry.delete(0, "end")
        self.video_info = None
        self.existing_song = None
        self.thumbnail_label.configure(image=self.preview_image)
        self.inspect_button.configure(state="disabled")
        self.download_button.configure(state="disabled")
        self.set_status("正在解析影片資訊...")
        future = self.executor.submit(self.youtube_service.get_single_video_info, url)
        future.add_done_callback(lambda done: self._safe_after(self._handle_video_info_loaded, done))

    def _handle_video_info_loaded(self, future) -> None:
        self.inspect_button.configure(state="normal")
        try:
            self.video_info = future.result()
        except Exception as exc:
            self.video_info = None
            self.set_status(str(exc), error=True)
            return
        self._render_video_info()
        self._load_thumbnail_async()
        self.download_button.configure(
            state="normal" if self.selected_artist and not self._is_existing_file_downloaded() else "disabled"
        )

    def _render_video_info(self) -> None:
        if self.video_info is None:
            return
        video = self.video_info.video
        self.existing_song = self.song_repository.get_by_video_id(video.youtube_video_id)
        self.title_label.configure(text=video.title)
        channel_text = self.video_info.channel_name or "未知"
        if self.video_info.channel_id:
            channel_text += f"\n{self.video_info.channel_id}"
        self.channel_label.configure(text=channel_text)
        self.duration_label.configure(text=self._format_duration(video.duration))

        if self._is_existing_file_downloaded():
            artist = self._find_artist_by_id(self.existing_song.artist_id)
            if artist:
                self.selected_artist = artist
                self.artist_menu.set(self._artist_label(artist))
            self.match_label.configure(
                text=f"已下載：{self.existing_song.song_name} / {self.existing_song.artist_id}"
            )
            self.download_button.configure(state="disabled")
            self.set_status("這首歌已下載，不能重複下載。", error=True)
            return

        matched = self._find_artist_by_channel_id(self.video_info.channel_id)
        if matched:
            self.selected_artist = matched
            self.artist_menu.set(self._artist_label(matched))
            self.match_label.configure(text=f"自動比對成功：{matched.channel_name} / {matched.artist_id}")
            if self.existing_song:
                self.set_status("資料庫有這首歌的紀錄，但檔案不存在，可以重新下載。", error=True)
            else:
                self.set_status("已自動選擇歌手，可以下載。")
            return
        self.selected_artist = None
        self.artist_menu.set(self.ARTIST_PLACEHOLDER)
        self.match_label.configure(text="找不到相同 channel ID 的歌手，請手動選擇歌手。")
        if self.existing_song:
            self.set_status("資料庫有這首歌的紀錄，但檔案不存在；請選擇歌手後重新下載。", error=True)
        else:
            self.set_status("歌手是必填，請選擇歌手後再下載。", error=True)

    def _load_thumbnail_async(self) -> None:
        if self.video_info is None:
            return
        video = self.video_info.video
        future = self.executor.submit(
            self.thumbnail_service.get_thumbnail,
            video.youtube_video_id,
            video.thumbnail_url,
        )
        future.add_done_callback(
            lambda done, video_id=video.youtube_video_id: self._safe_after(
                self._handle_thumbnail_loaded,
                video_id,
                done,
            )
        )

    def _handle_thumbnail_loaded(self, video_id: str, future) -> None:
        if self.video_info is None or self.video_info.video.youtube_video_id != video_id:
            return
        try:
            image = future.result()
        except Exception:
            return
        if image is None:
            return
        self.preview_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=self._fit_image_size(image.size, SINGLE_PREVIEW_SIZE),
        )
        self.thumbnail_label.configure(image=self.preview_image)

    def download_video(self) -> None:
        if self.video_info is None:
            self.set_status("請先解析影片資訊。", error=True)
            return
        if self.selected_artist is None:
            self.set_status("歌手是必填，請選擇歌手。", error=True)
            return
        if self._is_existing_file_downloaded():
            self.download_button.configure(state="disabled")
            self.set_status("這首歌已下載，不能重複下載。", error=True)
            return
        self.download_button.configure(state="disabled")
        self.inspect_button.configure(state="disabled")
        self.set_status("下載進度：0/1")
        future = self.executor.submit(
            self.download_service.download_video,
            self.selected_artist,
            self.video_info.video,
            self._threadsafe_status,
        )
        future.add_done_callback(lambda done: self._safe_after(self._handle_download_finished, done))

    def _handle_download_finished(self, future) -> None:
        self.inspect_button.configure(state="normal")
        self.download_button.configure(
            state="normal" if self.video_info and self.selected_artist and not self._is_existing_file_downloaded() else "disabled"
        )
        try:
            ok = future.result()
        except Exception as exc:
            self.set_status(f"下載失敗：{exc}", error=True)
            return
        self.set_status("下載進度：1/1，完成。" if ok else "下載進度：1/1，已略過。")
        if self.video_info:
            self.existing_song = self.song_repository.get_by_video_id(self.video_info.video.youtube_video_id)
        if self.on_downloads_changed:
            self.on_downloads_changed()
        if self._is_existing_file_downloaded():
            self.download_button.configure(state="disabled")

    def _threadsafe_status(self, _video_id: str, status: str) -> None:
        self._safe_after(self.set_status, status)

    def _artist_selected(self, label: str) -> None:
        for artist in self.artists:
            if self._artist_label(artist) == label:
                self.selected_artist = artist
                self.download_button.configure(
                    state="normal" if self.video_info and not self._is_existing_file_downloaded() else "disabled"
                )
                return
        self.selected_artist = None
        self.download_button.configure(state="disabled")

    def _find_artist_by_channel_id(self, channel_id: str | None) -> Artist | None:
        if not channel_id:
            return None
        for artist in self.artists:
            if artist.channel_id == channel_id:
                return artist
        return None

    def _find_artist_by_id(self, artist_id: str) -> Artist | None:
        for artist in self.artists:
            if artist.artist_id == artist_id:
                return artist
        return None

    def _artist_label(self, artist: Artist) -> str:
        return f"{artist.channel_name} / {artist.artist_id}"

    def _is_existing_file_downloaded(self) -> bool:
        return self.existing_song is not None and Path(self.existing_song.file_path).exists()

    def _make_default_thumbnail(self) -> ctk.CTkImage:
        image = Image.new("RGB", SINGLE_PREVIEW_SIZE, "#1f1f1f")
        return ctk.CTkImage(light_image=image, dark_image=image, size=SINGLE_PREVIEW_SIZE)

    def _fit_image_size(self, image_size: tuple[int, int], max_size: tuple[int, int]) -> tuple[int, int]:
        width, height = image_size
        max_width, max_height = max_size
        if width <= 0 or height <= 0:
            return max_size
        scale = min(max_width / width, max_height / height)
        return max(1, int(width * scale)), max(1, int(height * scale))

    def _format_duration(self, duration: int | None) -> str:
        if duration is None:
            return "未知"
        minutes, seconds = divmod(int(duration), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def _safe_after(self, callback, *args) -> None:
        if self.is_destroyed:
            return
        try:
            self.after(0, callback, *args)
        except Exception:
            return

    def destroy(self) -> None:
        self.is_destroyed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
