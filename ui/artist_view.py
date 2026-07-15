import re
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image, ImageDraw

from config import APP_FONT_FAMILY, CHANNEL_AVATAR_SIZE
from database.artist_repository import ArtistRepository
from database.tag_repository import TagRepository
from models.artist import Artist
from services.thumbnail_service import ThumbnailService
from services.youtube_service import ChannelInfo
from services.youtube_service import YouTubeService
from ui.fonts import base_font, button_font, large_title_font, small_title_font, title_font

ARTIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
ARTIST_CARD_COLUMNS = 3
ARTIST_CARD_WIDTH = 360
ARTIST_CARD_HEIGHT = 132
ARTIST_CARD_TEXT_WIDTH = 160


class ArtistView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        artist_repository: ArtistRepository,
        youtube_service: YouTubeService,
        thumbnail_service: ThumbnailService,
        tag_repository: TagRepository,
        on_artists_changed,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.youtube_service = youtube_service
        self.thumbnail_service = thumbnail_service
        self.tag_repository = tag_repository
        self.on_artists_changed = on_artists_changed
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.channel_name_entries: dict[str, ctk.CTkEntry] = {}
        self.tag_vars: dict[int, ctk.BooleanVar] = {}
        self.artist_avatar_labels: dict[str, ctk.CTkLabel] = {}
        self.artist_avatar_images: dict[str, ctk.CTkImage] = {}
        self.avatar_requests: set[str] = set()
        self.editing_artist_id: str | None = None
        self.preview_channel: ChannelInfo | None = None
        self.editing_artist: Artist | None = None
        self.preview_avatar_image = self._make_default_avatar()
        self.is_destroyed = False
        self.font = base_font()
        self.button_font = button_font()
        self.bold_font = small_title_font()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.add_page = ctk.CTkFrame(self, fg_color="transparent")
        self.add_page.grid(row=0, column=0, sticky="nsew")
        self.add_page.grid_columnconfigure(0, weight=1)
        self.add_page.grid_columnconfigure(1, weight=0, minsize=560)
        self.add_page.grid_rowconfigure(0, weight=1)

        self.list_page = ctk.CTkFrame(self, fg_color="transparent")
        self.list_page.grid(row=0, column=0, sticky="nsew")
        self.list_page.grid_columnconfigure(0, weight=1)
        self.list_page.grid_rowconfigure(0, weight=1)

        self.edit_page = ctk.CTkScrollableFrame(self)
        self.edit_page.grid(row=0, column=0, sticky="nsew")
        self.edit_page.grid_columnconfigure(1, weight=1)

        form = ctk.CTkFrame(self.add_page)
        form.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="id", font=self.font).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 6))
        self.artist_id_entry = ctk.CTkEntry(form, placeholder_text="例如 suisei", font=self.font)
        self.artist_id_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8), pady=(18, 6))
        self.id_status_label = ctk.CTkLabel(form, text="✓ 顯示 id 是否可使用", anchor="w", font=self.font)
        self.id_status_label.grid(row=0, column=2, sticky="w", padx=(0, 18), pady=(18, 6))

        ctk.CTkLabel(form, text="連結", font=self.font).grid(row=1, column=0, sticky="w", padx=18, pady=6)
        self.url_entry = ctk.CTkEntry(form, placeholder_text="https://www.youtube.com/@channel", font=self.font)
        self.url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 18), pady=6)
        self.url_entry.bind("<KeyRelease>", lambda _event: self._clear_preview_if_url_changed())

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(row=2, column=0, columnspan=3, sticky="ew", padx=18, pady=(8, 18))
        buttons.grid_columnconfigure((0, 1), weight=1)
        self.preview_button = ctk.CTkButton(buttons, text="預覽頻道", command=self.preview_channel_info, font=self.button_font)
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.add_button = ctk.CTkButton(buttons, text="新增頻道", command=self.add_artist, font=self.button_font)
        self.add_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.future_label = ctk.CTkLabel(
            form,
            text="未來的其他\n新增歌手資訊",
            font=title_font(),
            justify="center",
        )
        self.future_label.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=18, pady=28)
        form.grid_rowconfigure(3, weight=1)

        self.status_label = ctk.CTkLabel(form, text="", anchor="w", font=self.font)
        self.status_label.grid(row=4, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 18))

        self.preview_frame = ctk.CTkFrame(self.add_page)
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 8), pady=8)
        self.preview_frame.grid_propagate(False)
        self.preview_frame.grid_columnconfigure(1, weight=1)
        self.preview_avatar_label = ctk.CTkLabel(self.preview_frame, image=self.preview_avatar_image, text="")
        self.preview_avatar_label.grid(row=0, column=0, rowspan=2, padx=18, pady=24)
        self.preview_title_label = ctk.CTkLabel(
            self.preview_frame,
            text="頻道名",
            anchor="w",
            justify="left",
            wraplength=400,
            font=large_title_font(),
        )
        self.preview_title_label.grid(row=0, column=1, sticky="ew", padx=(8, 18), pady=(28, 4))
        self.preview_detail_label = ctk.CTkLabel(
            self.preview_frame,
            text="影片數：未知",
            anchor="w",
            justify="left",
            wraplength=400,
            font=self.bold_font,
        )
        self.preview_detail_label.grid(row=1, column=1, sticky="new", padx=(8, 18), pady=(4, 18))

        self.artist_list = ctk.CTkScrollableFrame(self.list_page)
        self.artist_list.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.artist_list.grid_columnconfigure(0, weight=1)
        self.reload_artists()
        self.show_list_page()

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

    def show_add_page(self) -> None:
        self.edit_page.grid_remove()
        self.list_page.grid_remove()
        self.add_page.grid()

    def show_list_page(self) -> None:
        self.reload_artists()
        self.edit_page.grid_remove()
        self.add_page.grid_remove()
        self.list_page.grid()

    def show_edit_page(self, artist: Artist) -> None:
        self.editing_artist = artist
        self.render_edit_page()
        self.add_page.grid_remove()
        self.list_page.grid_remove()
        self.edit_page.grid()

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
        for column in range(ARTIST_CARD_COLUMNS):
            self.artist_list.grid_columnconfigure(column, weight=1, uniform="artist_cards")
        for index, artist in enumerate(artists):
            row = index // ARTIST_CARD_COLUMNS
            column = index % ARTIST_CARD_COLUMNS
            frame = ctk.CTkFrame(self.artist_list)
            frame.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            frame.configure(width=ARTIST_CARD_WIDTH, height=ARTIST_CARD_HEIGHT)
            frame.grid_propagate(False)
            frame.grid_columnconfigure(1, weight=1)
            frame.grid_rowconfigure(0, weight=1)

            avatar_label = ctk.CTkLabel(frame, image=self._make_default_avatar(), text="")
            avatar_label.grid(row=0, column=0, padx=(10, 8), pady=10)
            self.artist_avatar_labels[artist.artist_id] = avatar_label
            if artist.artist_id in self.artist_avatar_images:
                avatar_label.configure(image=self.artist_avatar_images[artist.artist_id])
            else:
                self._load_artist_avatar_async(artist)

            text_frame = ctk.CTkFrame(frame, fg_color="transparent")
            text_frame.grid(row=0, column=1, sticky="ew", padx=6, pady=10)
            text_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                text_frame,
                text=artist.channel_name,
                anchor="w",
                wraplength=ARTIST_CARD_TEXT_WIDTH,
                font=self.font,
            ).grid(
                row=0, column=0, sticky="ew"
            )
            ctk.CTkLabel(
                text_frame,
                text=artist.artist_id,
                anchor="w",
                wraplength=ARTIST_CARD_TEXT_WIDTH,
                font=self.font,
            ).grid(
                row=1, column=0, sticky="ew", pady=(4, 0)
            )
            ctk.CTkButton(
                frame,
                text="編輯",
                width=72,
                command=lambda selected_artist=artist: self.show_edit_page(selected_artist),
                font=self.button_font,
            ).grid(row=0, column=2, padx=(6, 10), pady=10)

    def _load_artist_avatar_async(self, artist) -> None:
        if artist.artist_id in self.avatar_requests and artist.artist_id not in self.artist_avatar_images:
            return
        self.avatar_requests.add(artist.artist_id)
        future = self.executor.submit(self._artist_avatar_worker, artist)
        future.add_done_callback(
            lambda done, artist_id=artist.artist_id: self._safe_after(
                self._handle_artist_avatar_loaded, artist_id, done
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
        try:
            image = future.result()
        except Exception:
            image = None
        if image is None:
            self.avatar_requests.discard(artist_id)
            return
        photo = ctk.CTkImage(light_image=image, dark_image=image, size=CHANNEL_AVATAR_SIZE)
        self.artist_avatar_images[artist_id] = photo
        label = self.artist_avatar_labels.get(artist_id)
        if label is None:
            return
        label.configure(image=photo)

    def preview_channel_info(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            self.set_status("請先輸入 YouTube 頻道網址。", error=True)
            return
        self.preview_button.configure(state="disabled")
        self.set_status("正在預覽頻道...")
        future = self.executor.submit(self._preview_worker, url)
        future.add_done_callback(lambda done: self._safe_after(self._handle_preview_result, done))

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
            self.preview_avatar_image = ctk.CTkImage(
                light_image=avatar,
                dark_image=avatar,
                size=CHANNEL_AVATAR_SIZE,
            )
        else:
            self.preview_avatar_image = self._make_default_avatar()
        self.preview_avatar_label.configure(image=self.preview_avatar_image)
        if channel is None:
            self.preview_title_label.configure(text="頻道名")
            self.preview_detail_label.configure(text="影片數：未知")
            return
        count = f"{channel.video_count:,}" if channel.video_count is not None else "未知"
        self.preview_title_label.configure(text=channel.channel_name)
        self.preview_detail_label.configure(text=f"影片數：約 {count} 部\nChannel ID：{channel.channel_id}")

    def _clear_preview_if_url_changed(self) -> None:
        if self.preview_channel and self.preview_channel.input_url != self.url_entry.get().strip():
            self.preview_channel = None
            self._render_preview(None)

    def render_edit_page(self) -> None:
        for child in self.edit_page.winfo_children():
            child.destroy()
        self.tag_vars.clear()
        artist = self.editing_artist
        if artist is None:
            return
        ctk.CTkLabel(self.edit_page, text=f"編輯歌手：{artist.artist_id}", font=self.bold_font).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(self.edit_page, text="頻道名稱", font=self.font).grid(
            row=1, column=0, sticky="w", padx=12, pady=8
        )
        self.edit_channel_name_entry = ctk.CTkEntry(self.edit_page, font=self.font)
        self.edit_channel_name_entry.insert(0, artist.channel_name)
        self.edit_channel_name_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(self.edit_page, text="標籤", font=self.bold_font).grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(18, 8)
        )
        selected_option_ids = self.tag_repository.get_artist_option_ids(artist.artist_id)
        row = 3
        for category in self.tag_repository.list_categories():
            options = self.tag_repository.list_options_by_category(category.id)
            category_frame = ctk.CTkFrame(self.edit_page)
            category_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=6)
            category_frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(category_frame, text=category.name, width=100, anchor="w", font=self.font).grid(
                row=0, column=0, sticky="nw", padx=10, pady=10
            )
            options_frame = ctk.CTkFrame(category_frame, fg_color="transparent")
            options_frame.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
            if not options:
                ctk.CTkLabel(options_frame, text="尚無下層標籤", font=self.font).pack(
                    side="left", padx=4, pady=4
                )
            for option in options:
                var = ctk.BooleanVar(value=option.id in selected_option_ids)
                self.tag_vars[option.id] = var
                ctk.CTkCheckBox(
                    options_frame,
                    text=option.name,
                    variable=var,
                    font=self.font,
                ).pack(side="left", padx=6, pady=4)
            row += 1

        buttons = ctk.CTkFrame(self.edit_page, fg_color="transparent")
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", padx=12, pady=14)
        ctk.CTkButton(
            buttons,
            text="儲存",
            font=self.button_font,
            command=self.save_artist_edit,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            buttons,
            text="取消",
            font=self.button_font,
            command=self.show_list_page,
        ).pack(side="left", padx=6)

    def save_artist_edit(self) -> None:
        artist = self.editing_artist
        if artist is None:
            return
        try:
            updated = self.artist_repository.update_channel_name(
                artist.artist_id,
                self.edit_channel_name_entry.get(),
            )
            selected = {option_id for option_id, var in self.tag_vars.items() if var.get()}
            self.tag_repository.replace_artist_tags(artist.artist_id, selected)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.editing_artist = updated
        self.set_status(f"已更新歌手：{updated.artist_id} / {updated.channel_name}")
        self.on_artists_changed()
        self.show_list_page()

    def _make_default_avatar(self):
        image = Image.new("RGB", CHANNEL_AVATAR_SIZE, "#d9dee8")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, CHANNEL_AVATAR_SIZE[0] - 8, CHANNEL_AVATAR_SIZE[1] - 8), fill="#b7c0d1")
        draw.text((30, 40), "CH", fill="#4a5568")
        return ctk.CTkImage(light_image=image, dark_image=image, size=CHANNEL_AVATAR_SIZE)

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def destroy(self) -> None:
        self.is_destroyed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()

    def _safe_after(self, callback, *args) -> None:
        if self.is_destroyed:
            return
        try:
            self.after(0, callback, *args)
        except Exception:
            return
