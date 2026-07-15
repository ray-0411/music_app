from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image, ImageDraw

from config import APP_FONT_FAMILY, DOWNLOADS_DIR, THUMBNAIL_SIZE
from database.artist_repository import ArtistRepository
from database.song_repository import SongRepository
from database.tag_repository import TagRepository
from models.song import Song
from services.song_service import SongService
from services.thumbnail_service import ThumbnailService
from ui.fonts import base_font, button_font
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
        tag_repository: TagRepository,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.song_repository = song_repository
        self.song_service = song_service
        self.thumbnail_service = thumbnail_service
        self.tag_repository = tag_repository
        self.tag_vars: dict[int, ctk.BooleanVar] = {}
        self.thumbnail_labels: dict[str, ctk.CTkLabel] = {}
        self.thumbnail_images: dict[str, ctk.CTkImage] = {}
        self.thumbnail_requests: set[str] = set()
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=4)
        self.default_thumbnail = self._make_default_thumbnail()
        self.is_destroyed = False
        self.editing_song: Song | None = None
        self.font = base_font()
        self.button_font = button_font()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.refresh_button = ctk.CTkButton(toolbar, text="重新整理", command=self.reload_songs, font=self.button_font)
        self.refresh_button.pack(side="left", padx=12, pady=10)
        self.status_label = ctk.CTkLabel(toolbar, text="", anchor="w", font=self.font)
        self.status_label.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        self.list_page = ctk.CTkFrame(self, fg_color="transparent")
        self.list_page.grid(row=1, column=0, sticky="nsew")
        self.list_page.grid_columnconfigure(0, weight=1)
        self.list_page.grid_rowconfigure(0, weight=1)

        self.edit_page = ctk.CTkScrollableFrame(self)
        self.edit_page.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.edit_page.grid_columnconfigure(1, weight=1)

        self.song_list = ctk.CTkScrollableFrame(self.list_page)
        self.song_list.grid(row=0, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.song_list.grid_columnconfigure(0, weight=1)
        self.reload_songs()
        self.show_list_page()

    def reload_songs(self) -> None:
        for child in self.song_list.winfo_children():
            child.destroy()
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
        frame.grid_rowconfigure((0, 1), weight=1)

        thumb_label = ctk.CTkLabel(frame, image=self.default_thumbnail, text="")
        thumb_label.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=10)
        self.thumbnail_labels[song.youtube_video_id] = thumb_label
        if song.youtube_video_id in self.thumbnail_images:
            thumb_label.configure(image=self.thumbnail_images[song.youtube_video_id])
        else:
            image = self.thumbnail_service.get_existing_song_thumbnail(song.youtube_video_id)
            if image is not None:
                photo = ctk.CTkImage(light_image=image, dark_image=image, size=THUMBNAIL_SIZE)
                self.thumbnail_images[song.youtube_video_id] = photo
                thumb_label.configure(image=photo)
            else:
                self._load_song_thumbnail_async(song)

        status = self._song_status(song)
        artist_name = artist_names.get(song.artist_id.lower(), song.artist_id)
        ctk.CTkLabel(frame, text=artist_name, width=140, anchor="w", font=self.font).grid(
            row=0, column=1, rowspan=2, sticky="nsew", padx=(6, 6), pady=10
        )

        ctk.CTkLabel(frame, text=self._display_song_name(song), anchor="w", font=self.font).grid(
            row=0, column=2, sticky="nsew", padx=6, pady=(10, 4)
        )
        ctk.CTkButton(
            frame,
            text="編輯",
            width=72,
            command=lambda selected_song=song: self.show_edit_page(selected_song),
            font=self.button_font,
        ).grid(row=0, column=3, rowspan=2, padx=(6, 10), pady=10)
        ctk.CTkLabel(frame, text=f"長度：{self._display_duration(song.duration)}", anchor="w", font=self.font).grid(
            row=1, column=2, sticky="nsew", padx=6, pady=(0, 10)
        )

    def render_edit_page(self) -> None:
        for child in self.edit_page.winfo_children():
            child.destroy()
        self.tag_vars.clear()
        song = self.editing_song
        if song is None:
            return

        ctk.CTkLabel(self.edit_page, text=f"編輯歌曲：{self._display_song_name(song)}", anchor="w", font=self.font).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(self.edit_page, text="歌曲名稱", anchor="w", font=self.font).grid(
            row=1, column=0, sticky="w", padx=12, pady=8
        )
        self.song_name_entry = ctk.CTkEntry(self.edit_page, font=self.font)
        self.song_name_entry.insert(0, self._display_song_name(song))
        self.song_name_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(self.edit_page, text="原始 YouTube 標題", anchor="w", font=self.font).grid(
            row=2, column=0, sticky="nw", padx=12, pady=8
        )
        ctk.CTkLabel(
            self.edit_page,
            text=song.original_title,
            anchor="w",
            justify="left",
            wraplength=760,
            font=self.font,
        ).grid(row=2, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(self.edit_page, text="檔案", anchor="w", font=self.font).grid(
            row=3, column=0, sticky="nw", padx=12, pady=8
        )
        ctk.CTkLabel(
            self.edit_page,
            text=self._display_file_path(song.file_path),
            anchor="w",
            justify="left",
            wraplength=760,
            font=self.font,
        ).grid(row=3, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(self.edit_page, text="歌曲長度", anchor="w", font=self.font).grid(
            row=4, column=0, sticky="nw", padx=12, pady=8
        )
        ctk.CTkLabel(self.edit_page, text=self._display_duration(song.duration), anchor="w", font=self.font).grid(
            row=4, column=1, sticky="ew", padx=12, pady=8
        )

        ctk.CTkLabel(self.edit_page, text="上傳日期", anchor="w", font=self.font).grid(
            row=5, column=0, sticky="nw", padx=12, pady=8
        )
        ctk.CTkLabel(self.edit_page, text=self._display_upload_date(song.upload_date), anchor="w", font=self.font).grid(
            row=5, column=1, sticky="ew", padx=12, pady=8
        )

        ctk.CTkLabel(self.edit_page, text="狀態", anchor="w", font=self.font).grid(
            row=6, column=0, sticky="nw", padx=12, pady=8
        )
        ctk.CTkLabel(self.edit_page, text=self._song_status(song), anchor="w", font=self.font).grid(
            row=6, column=1, sticky="ew", padx=12, pady=8
        )

        ctk.CTkLabel(self.edit_page, text="標籤", anchor="w", font=self.font).grid(
            row=7, column=0, sticky="nw", padx=12, pady=(14, 8)
        )
        tag_frame = ctk.CTkFrame(self.edit_page, fg_color="transparent")
        tag_frame.grid(row=7, column=1, sticky="ew", padx=12, pady=(10, 8))
        tag_frame.grid_columnconfigure(1, weight=1)
        self._render_tag_editor(tag_frame, song)

        buttons = ctk.CTkFrame(self.edit_page, fg_color="transparent")
        buttons.grid(row=8, column=1, sticky="w", padx=12, pady=(10, 16))
        ctk.CTkButton(
            buttons,
            text="儲存",
            command=self.save_song_edit,
            font=self.button_font,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="取消",
            command=self.show_list_page,
            font=self.button_font,
        ).pack(side="left", padx=8)

    def _render_tag_editor(self, tag_frame: ctk.CTkFrame, song: Song) -> None:
        if song.id is None:
            return
        selected_option_ids = self.tag_repository.get_song_option_ids(song.id)
        row = 0
        categories = self.tag_repository.list_categories()
        if not categories:
            ctk.CTkLabel(tag_frame, text="尚無歌曲標籤分類", anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", pady=4
            )
            return
        for category in categories:
            options = self.tag_repository.list_options_by_category(category.id)
            ctk.CTkLabel(tag_frame, text=category.name, anchor="w", font=self.font).grid(
                row=row, column=0, sticky="nw", padx=(0, 8), pady=4
            )
            options_frame = ctk.CTkFrame(tag_frame, fg_color="transparent")
            options_frame.grid(row=row, column=1, sticky="ew", pady=2)
            if not options:
                ctk.CTkLabel(options_frame, text="尚無下層標籤", anchor="w", font=self.font).grid(
                    row=0, column=0, sticky="w", padx=4, pady=2
                )
            for index, option in enumerate(options):
                var = ctk.BooleanVar(value=option.id in selected_option_ids)
                self.tag_vars[option.id] = var
                ctk.CTkCheckBox(
                    options_frame,
                    text=option.name,
                    variable=var,
                    onvalue=True,
                    offvalue=False,
                    font=self.font,
                ).grid(row=index // 3, column=index % 3, sticky="w", padx=4, pady=2)
            row += 1

    def _load_song_thumbnail_async(self, song: Song) -> None:
        if (
            song.youtube_video_id in self.thumbnail_requests
            and song.youtube_video_id not in self.thumbnail_images
        ):
            return
        self.thumbnail_requests.add(song.youtube_video_id)
        future = self.thumbnail_executor.submit(
            self.thumbnail_service.get_song_thumbnail, song.youtube_video_id, song.thumbnail_url
        )
        future.add_done_callback(
            lambda done, video_id=song.youtube_video_id: self._safe_after(
                self._handle_thumbnail_loaded, video_id, done
            )
        )

    def _handle_thumbnail_loaded(self, video_id: str, future) -> None:
        try:
            image = future.result()
        except Exception:
            image = None
        if image is None:
            self.thumbnail_requests.discard(video_id)
            return
        photo = ctk.CTkImage(light_image=image, dark_image=image, size=THUMBNAIL_SIZE)
        self.thumbnail_images[video_id] = photo
        label = self.thumbnail_labels.get(video_id)
        if label is None:
            return
        label.configure(image=photo)

    def show_list_page(self) -> None:
        self.edit_page.grid_remove()
        self.list_page.grid()
        self.editing_song = None
        self.tag_vars.clear()
        self.reload_songs()

    def show_edit_page(self, song: Song) -> None:
        self.editing_song = song
        self.render_edit_page()
        self.list_page.grid_remove()
        self.edit_page.grid()

    def save_song_edit(self) -> None:
        song = self.editing_song
        if song is None or song.id is None:
            self.set_status("找不到歌曲 ID。", error=True)
            return
        try:
            updated = self.song_service.rename_song(song.id, self.song_name_entry.get())
            selected = {option_id for option_id, var in self.tag_vars.items() if var.get()}
            self.tag_repository.replace_song_tags(song.id, selected)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.editing_song = None
        self.tag_vars.clear()
        self.set_status(f"已更新歌曲：{updated.file_name}")
        self.show_list_page()

    def _song_status(self, song: Song) -> str:
        if song.download_status == "downloaded" and not Path(song.file_path).exists():
            return "檔案遺失"
        return song.download_status

    def _display_song_name(self, song: Song) -> str:
        return build_song_name(song.artist_id, song.song_name)

    def _display_duration(self, duration: int | None) -> str:
        if duration is None:
            return "未知"
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _display_upload_date(self, upload_date: str | None) -> str:
        if not upload_date:
            return "未知"
        cleaned = upload_date.strip()
        if len(cleaned) == 8 and cleaned.isdigit():
            return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:]}"
        return cleaned.replace("/", "-")

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
        return ctk.CTkImage(light_image=image, dark_image=image, size=THUMBNAIL_SIZE)

    def _safe_after(self, callback, *args) -> None:
        if self.is_destroyed:
            return
        try:
            self.after(0, callback, *args)
        except Exception:
            return

    def destroy(self) -> None:
        self.is_destroyed = True
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
