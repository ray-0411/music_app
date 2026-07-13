import re
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from config import APP_FONT_FAMILY, CHANNEL_AVATAR_SIZE
from database.artist_repository import ArtistRepository
from services.thumbnail_service import ThumbnailService
from services.youtube_service import ChannelInfo
from services.youtube_service import YouTubeService

ARTIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class ArtistView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        artist_repository: ArtistRepository,
        youtube_service: YouTubeService,
        thumbnail_service: ThumbnailService,
        on_artists_changed,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.youtube_service = youtube_service
        self.thumbnail_service = thumbnail_service
        self.on_artists_changed = on_artists_changed
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.channel_name_entries: dict[str, ctk.CTkEntry] = {}
        self.artist_avatar_labels: dict[str, ctk.CTkLabel] = {}
        self.artist_avatar_images: dict[str, ImageTk.PhotoImage] = {}
        self.avatar_requests: set[str] = set()
        self.editing_artist_id: str | None = None
        self.preview_channel: ChannelInfo | None = None
        self.preview_avatar_image = self._make_default_avatar()
        self.font = ctk.CTkFont(family=APP_FONT_FAMILY, size=13)
        self.bold_font = ctk.CTkFont(family=APP_FONT_FAMILY, size=16, weight="bold")

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        form = ctk.CTkFrame(self)
        form.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="歌手 ID", font=self.font).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.artist_id_entry = ctk.CTkEntry(form, placeholder_text="例如 suisei", font=self.font)
        self.artist_id_entry.grid(row=0, column=1, sticky="ew", padx=12, pady=(12, 6))

        ctk.CTkLabel(form, text="YouTube 頻道網址", font=self.font).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.url_entry = ctk.CTkEntry(form, placeholder_text="https://www.youtube.com/@channel", font=self.font)
        self.url_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        self.url_entry.bind("<KeyRelease>", lambda _event: self._clear_preview_if_url_changed())

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(row=2, column=1, sticky="e", padx=12, pady=(6, 12))
        self.preview_button = ctk.CTkButton(buttons, text="預覽頻道", command=self.preview_channel_info, font=self.font)
        self.preview_button.pack(side="left", padx=(0, 8))
        self.add_button = ctk.CTkButton(buttons, text="新增歌手", command=self.add_artist, font=self.font)
        self.add_button.pack(side="left")

        self.status_label = ctk.CTkLabel(form, text="", anchor="w", font=self.font)
        self.status_label.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))

        self.preview_frame = ctk.CTkFrame(self)
        self.preview_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self.preview_frame.grid_columnconfigure(1, weight=1)
        self.preview_avatar_label = ctk.CTkLabel(self.preview_frame, image=self.preview_avatar_image, text="")
        self.preview_avatar_label.grid(row=0, column=0, rowspan=2, padx=12, pady=12)
        self.preview_title_label = ctk.CTkLabel(
            self.preview_frame, text="尚未預覽頻道", anchor="w", font=self.bold_font
        )
        self.preview_title_label.grid(row=0, column=1, sticky="ew", padx=8, pady=(12, 2))
        self.preview_detail_label = ctk.CTkLabel(self.preview_frame, text="", anchor="w", justify="left", font=self.font)
        self.preview_detail_label.grid(row=1, column=1, sticky="ew", padx=8, pady=(2, 12))

        ctk.CTkLabel(self, text="已新增歌手", font=self.bold_font).grid(
            row=2, column=0, sticky="nw", padx=8, pady=(8, 0)
        )
        self.artist_list = ctk.CTkScrollableFrame(self)
        self.artist_list.grid(row=2, column=1, sticky="nsew", padx=8, pady=8)
        self.artist_list.grid_columnconfigure(0, weight=1)
        self.reload_artists()

    def add_artist(self) -> None:
        artist_id = self.artist_id_entry.get().strip()
        url = self.url_entry.get().strip()
        if not artist_id or not url:
            self.set_status("請輸入歌手 ID 與 YouTube 頻道網址。", error=True)
            return
        if not ARTIST_ID_PATTERN.fullmatch(artist_id):
            self.set_status("歌手 ID 只能包含英文字母、數字、底線與連字號。", error=True)
            return

        self.add_button.configure(state="disabled")
        self.set_status("正在新增歌手...")
        future = self.executor.submit(self._add_artist_worker, artist_id, url, self.preview_channel)
        future.add_done_callback(lambda done: self.after(0, self._handle_add_result, done))

    def _add_artist_worker(self, artist_id: str, url: str, preview: ChannelInfo | None):
        channel = preview if preview and preview.input_url == url else self.youtube_service.get_channel_info(url)
        return self.artist_repository.add_artist(
            artist_id=artist_id,
            youtube_url=channel.channel_url,
            channel_id=channel.channel_id,
            channel_name=channel.channel_name,
            avatar_url=channel.avatar_url,
        )

    def _handle_add_result(self, future) -> None:
        self.add_button.configure(state="normal")
        try:
            artist = future.result()
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.artist_id_entry.delete(0, "end")
        self.url_entry.delete(0, "end")
        self.preview_channel = None
        self._render_preview(None)
        self.set_status(f"已新增：{artist.artist_id} / {artist.channel_name}")
        self.reload_artists()
        self.on_artists_changed()

    def reload_artists(self) -> None:
        for child in self.artist_list.winfo_children():
            child.destroy()
        self.channel_name_entries.clear()
        self.artist_avatar_labels.clear()
        artists = self.artist_repository.list_artists()
        if not artists:
            ctk.CTkLabel(self.artist_list, text="尚未新增歌手", anchor="w").grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            return
        for row, artist in enumerate(artists):
            frame = ctk.CTkFrame(self.artist_list)
            frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
            frame.grid_columnconfigure(2, weight=1)

            avatar_label = ctk.CTkLabel(frame, image=self._make_default_avatar(), text="")
            avatar_label.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=10)
            self.artist_avatar_labels[artist.artist_id] = avatar_label
            if artist.artist_id in self.artist_avatar_images:
                avatar_label.configure(image=self.artist_avatar_images[artist.artist_id])
            else:
                self._load_artist_avatar_async(artist)

            ctk.CTkLabel(frame, text=artist.artist_id, width=110, anchor="w", font=self.font).grid(
                row=0, column=1, sticky="w", padx=(6, 6), pady=10
            )
            if self.editing_artist_id == artist.artist_id:
                entry = ctk.CTkEntry(frame, font=self.font)
                entry.insert(0, artist.channel_name)
                entry.grid(row=0, column=2, sticky="ew", padx=6, pady=10)
                self.channel_name_entries[artist.artist_id] = entry
                ctk.CTkButton(
                    frame,
                    text="儲存",
                    width=72,
                    command=lambda artist_id=artist.artist_id: self.update_channel_name(artist_id),
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
                ctk.CTkLabel(frame, text=artist.channel_name, anchor="w", font=self.font).grid(
                    row=0, column=2, sticky="ew", padx=6, pady=10
                )
                ctk.CTkButton(
                    frame,
                    text="編輯",
                    width=72,
                    command=lambda artist_id=artist.artist_id: self.start_edit(artist_id),
                    font=self.font,
                ).grid(row=0, column=3, padx=(6, 10), pady=10)
            ctk.CTkLabel(frame, text=artist.channel_id, anchor="w", font=self.font).grid(
                row=1, column=2, columnspan=3, sticky="ew", padx=6, pady=(0, 10)
            )

    def _load_artist_avatar_async(self, artist) -> None:
        if artist.artist_id in self.avatar_requests:
            return
        self.avatar_requests.add(artist.artist_id)
        future = self.executor.submit(self._artist_avatar_worker, artist)
        future.add_done_callback(
            lambda done, artist_id=artist.artist_id: self.after(
                0, self._handle_artist_avatar_loaded, artist_id, done
            )
        )

    def _artist_avatar_worker(self, artist):
        avatar_url = artist.avatar_url
        if not avatar_url:
            channel = self.youtube_service.get_channel_info(artist.youtube_url)
            avatar_url = channel.avatar_url
            self.artist_repository.update_avatar_url(artist.artist_id, avatar_url)
        return self.thumbnail_service.get_channel_avatar(artist.channel_id, avatar_url)

    def _handle_artist_avatar_loaded(self, artist_id: str, future) -> None:
        label = self.artist_avatar_labels.get(artist_id)
        if label is None:
            return
        try:
            image = future.result()
        except Exception:
            image = None
        if image is None:
            return
        photo = ImageTk.PhotoImage(image)
        self.artist_avatar_images[artist_id] = photo
        label.configure(image=photo)

    def preview_channel_info(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            self.set_status("請先輸入 YouTube 頻道網址。", error=True)
            return
        self.preview_button.configure(state="disabled")
        self.set_status("正在預覽頻道...")
        future = self.executor.submit(self._preview_worker, url)
        future.add_done_callback(lambda done: self.after(0, self._handle_preview_result, done))

    def _preview_worker(self, url: str):
        channel = self.youtube_service.get_channel_info(url)
        video_count = self.youtube_service.count_channel_videos(channel.channel_url)
        if video_count is not None:
            channel = ChannelInfo(
                input_url=channel.input_url,
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                channel_url=channel.channel_url,
                avatar_url=channel.avatar_url,
                video_count=video_count,
            )
        avatar = self.thumbnail_service.get_channel_avatar(channel.channel_id, channel.avatar_url)
        return channel, avatar

    def _handle_preview_result(self, future) -> None:
        self.preview_button.configure(state="normal")
        try:
            channel, avatar = future.result()
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.preview_channel = channel
        self._render_preview(channel, avatar)
        self.set_status("頻道預覽完成。")

    def _render_preview(self, channel: ChannelInfo | None, avatar=None) -> None:
        if avatar is not None:
            self.preview_avatar_image = ImageTk.PhotoImage(avatar)
        else:
            self.preview_avatar_image = self._make_default_avatar()
        self.preview_avatar_label.configure(image=self.preview_avatar_image)
        if channel is None:
            self.preview_title_label.configure(text="尚未預覽頻道")
            self.preview_detail_label.configure(text="")
            return
        count = f"{channel.video_count:,}" if channel.video_count is not None else "未知"
        self.preview_title_label.configure(text=channel.channel_name)
        self.preview_detail_label.configure(
            text=f"Channel ID：{channel.channel_id}\n影片總數：約 {count} 部\n{channel.channel_url}"
        )

    def _clear_preview_if_url_changed(self) -> None:
        if self.preview_channel and self.preview_channel.input_url != self.url_entry.get().strip():
            self.preview_channel = None
            self._render_preview(None)

    def start_edit(self, artist_id: str) -> None:
        self.editing_artist_id = artist_id
        self.reload_artists()

    def cancel_edit(self) -> None:
        self.editing_artist_id = None
        self.reload_artists()

    def update_channel_name(self, artist_id: str) -> None:
        entry = self.channel_name_entries.get(artist_id)
        if entry is None:
            self.set_status("找不到歌手欄位。", error=True)
            return
        try:
            artist = self.artist_repository.update_channel_name(artist_id, entry.get())
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.set_status(f"已更新名稱：{artist.artist_id} / {artist.channel_name}")
        self.editing_artist_id = None
        self.reload_artists()
        self.on_artists_changed()

    def _make_default_avatar(self):
        image = Image.new("RGB", CHANNEL_AVATAR_SIZE, "#d9dee8")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, CHANNEL_AVATAR_SIZE[0] - 8, CHANNEL_AVATAR_SIZE[1] - 8), fill="#b7c0d1")
        draw.text((30, 40), "CH", fill="#4a5568")
        return ImageTk.PhotoImage(image)

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def destroy(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
