from concurrent.futures import ThreadPoolExecutor
from functools import partial

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from config import APP_FONT_FAMILY, THUMBNAIL_SIZE, THUMBNAIL_WORKERS, VIDEO_BATCH_SIZE, VIDEO_PAGE_SIZE
from database.artist_repository import ArtistRepository
from database.song_repository import SongRepository
from models.artist import Artist
from models.video import Video
from services.download_service import DownloadService
from services.thumbnail_service import ThumbnailService
from services.youtube_service import YouTubeService


class VideoView(ctk.CTkFrame):
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
        self.worker_executor = ThreadPoolExecutor(max_workers=2)
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=THUMBNAIL_WORKERS)
        self.detail_executor = ThreadPoolExecutor(max_workers=4)

        self.artists: list[Artist] = []
        self.selected_artist: Artist | None = None
        self.videos: list[Video] = []
        self.filtered_videos: list[Video] = []
        self.current_page = 0
        self.total_count: int | None = None
        self.count_loading = False
        self.has_more = False
        self.loading_more = False
        self.count_loading = False
        self.selected: dict[str, ctk.BooleanVar] = {}
        self.rows: dict[str, dict] = {}
        self.details_requested: set[str] = set()
        self.default_thumbnail = self._make_default_thumbnail()
        self.font = ctk.CTkFont(family=APP_FONT_FAMILY, size=13)
        self.title_font = ctk.CTkFont(family=APP_FONT_FAMILY, size=14, weight="bold")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        toolbar.grid_columnconfigure(1, weight=1)
        toolbar.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(toolbar, text="歌手", font=self.font).grid(row=0, column=0, padx=(12, 6), pady=12)
        self.artist_menu = ctk.CTkOptionMenu(toolbar, values=["尚無歌手"], command=self._artist_selected, font=self.font)
        self.artist_menu.grid(row=0, column=1, sticky="ew", padx=6, pady=12)

        self.refresh_button = ctk.CTkButton(toolbar, text="取得 / 重新整理影片", command=self.load_videos, font=self.font)
        self.refresh_button.grid(row=0, column=2, padx=6, pady=12)

        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="搜尋影片標題", font=self.font)
        self.search_entry.grid(row=0, column=3, sticky="ew", padx=6, pady=12)
        self.search_entry.bind("<KeyRelease>", lambda _event: self.apply_filter())

        actions = ctk.CTkFrame(self)
        actions.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.select_all_button = ctk.CTkButton(actions, text="全選", width=88, command=self.select_all, font=self.font)
        self.select_all_button.pack(side="left", padx=(12, 6), pady=10)
        self.clear_button = ctk.CTkButton(actions, text="取消全選", width=88, command=self.clear_selection, font=self.font)
        self.clear_button.pack(side="left", padx=6, pady=10)
        self.download_button = ctk.CTkButton(actions, text="批次下載", width=110, command=self.download_selected, font=self.font)
        self.download_button.pack(side="left", padx=6, pady=10)
        self.prev_button = ctk.CTkButton(actions, text="上一頁", width=88, command=self.prev_page, font=self.font)
        self.prev_button.pack(side="left", padx=6, pady=10)
        self.next_button = ctk.CTkButton(actions, text="下一頁", width=88, command=self.next_page, font=self.font)
        self.next_button.pack(side="left", padx=6, pady=10)
        self.page_label = ctk.CTkLabel(actions, text="第 0 / 0 頁", font=self.font)
        self.page_label.pack(side="left", padx=6, pady=10)
        self.status_label = ctk.CTkLabel(actions, text="", anchor="w", font=self.font)
        self.status_label.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        self.video_list = ctk.CTkScrollableFrame(self)
        self.video_list.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.video_list.grid_columnconfigure(0, weight=1)

        self.reload_artists()

    def reload_artists(self) -> None:
        self.artists = self.artist_repository.list_artists()
        if not self.artists:
            self.artist_menu.configure(values=["尚無歌手"])
            self.artist_menu.set("尚無歌手")
            self.selected_artist = None
            return
        labels = [self._artist_label(artist) for artist in self.artists]
        self.artist_menu.configure(values=labels)
        if self.selected_artist is None:
            self.selected_artist = self.artists[0]
        else:
            matched = next(
                (
                    artist
                    for artist in self.artists
                    if artist.artist_id.lower() == self.selected_artist.artist_id.lower()
                ),
                None,
            )
            self.selected_artist = matched or self.artists[0]
        self.artist_menu.set(self._artist_label(self.selected_artist))

    def _artist_selected(self, label: str) -> None:
        for artist in self.artists:
            if self._artist_label(artist) == label:
                self.selected_artist = artist
                break

    def load_videos(self) -> None:
        if self.selected_artist is None:
            self.set_status("請先新增並選擇歌手。", error=True)
            return
        self.refresh_button.configure(state="disabled")
        self.current_page = 0
        self.videos = []
        self.filtered_videos = []
        self.total_count = None
        self.has_more = False
        self.loading_more = False
        self.render_videos()
        self.set_status(f"正在取得前 {VIDEO_BATCH_SIZE} 部影片...")
        future = self.worker_executor.submit(
            self._load_videos_worker, self.selected_artist, 0
        )
        future.add_done_callback(lambda done: self.after(0, self._handle_videos_loaded, done, False))

    def _load_videos_worker(self, artist: Artist, start: int):
        result = self.youtube_service.list_channel_videos(
            artist.youtube_url, start=start, limit=VIDEO_BATCH_SIZE
        )
        videos = self.song_repository.mark_video_states(artist.artist_id, result.videos)
        return result, videos

    def _handle_videos_loaded(self, future, append: bool) -> None:
        self.refresh_button.configure(state="normal")
        self.loading_more = False
        try:
            result, videos = future.result()
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        if append:
            existing_ids = {video.youtube_video_id for video in self.videos}
            self.videos.extend(video for video in videos if video.youtube_video_id not in existing_ids)
        else:
            self.videos = videos
        if result.total_count is not None:
            self.total_count = result.total_count
        self.has_more = result.limited
        self.apply_filter()
        total_text = f" / 頻道共約 {self.total_count} 部" if self.total_count else ""
        if self.total_count is None:
            total_text = " / 頻道影片總數：未知"
        notice = f"已載入 {len(self.videos)} 部影片{total_text}。"
        if self.has_more:
            notice += " 接近最後一頁時會自動載入下一批。"
        self.set_status(notice)
        if not append:
            self._load_total_count_async()

    def apply_filter(self) -> None:
        query = self.search_entry.get().strip().lower()
        if query:
            self.filtered_videos = [video for video in self.videos if query in video.title.lower()]
        else:
            self.filtered_videos = list(self.videos)
        self.current_page = min(self.current_page, max(self.page_count() - 1, 0))
        self.render_videos()

    def render_videos(self) -> None:
        for child in self.video_list.winfo_children():
            child.destroy()
        self.rows.clear()
        self.selected.clear()
        if not self.filtered_videos:
            self.page_label.configure(text="第 0 / 0 頁")
            ctk.CTkLabel(self.video_list, text="尚無影片資料", anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            return
        page_start = self.current_page * VIDEO_PAGE_SIZE
        page_end = page_start + VIDEO_PAGE_SIZE
        page_videos = self.filtered_videos[page_start:page_end]
        self.page_label.configure(text=f"第 {self.current_page + 1} / {self.page_count()} 頁")
        self.prev_button.configure(state="normal" if self.current_page > 0 else "disabled")
        can_next = page_end < len(self.filtered_videos) or self.has_more
        self.next_button.configure(state="normal" if can_next else "disabled")
        for row_index, video in enumerate(page_videos):
            self._render_video_row(row_index, video)
        self._maybe_load_next_batch()
        self._load_visible_video_details(page_videos)

    def page_count(self) -> int:
        if not self.filtered_videos:
            return 0
        return (len(self.filtered_videos) + VIDEO_PAGE_SIZE - 1) // VIDEO_PAGE_SIZE

    def next_page(self) -> None:
        next_index = self.current_page + 1
        if next_index < self.page_count():
            self.current_page = next_index
            self.render_videos()
            return
        if self.has_more:
            self._load_next_batch()

    def prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self.render_videos()

    def _maybe_load_next_batch(self) -> None:
        if self.search_entry.get().strip():
            return
        page_end = (self.current_page + 1) * VIDEO_PAGE_SIZE
        if self.has_more and page_end >= len(self.videos) - VIDEO_PAGE_SIZE:
            self._load_next_batch()

    def _load_next_batch(self) -> None:
        if self.loading_more or self.selected_artist is None:
            return
        self.loading_more = True
        start = len(self.videos)
        self.set_status(f"正在載入第 {start + 1} 到 {start + VIDEO_BATCH_SIZE} 部影片...")
        future = self.worker_executor.submit(
            self._load_videos_worker, self.selected_artist, start
        )
        future.add_done_callback(lambda done: self.after(0, self._handle_videos_loaded, done, True))

    def _load_total_count_async(self) -> None:
        if self.selected_artist is None or self.count_loading:
            return
        self.count_loading = True
        artist = self.selected_artist
        future = self.worker_executor.submit(
            self.youtube_service.count_channel_videos, artist.youtube_url
        )
        future.add_done_callback(lambda done: self.after(0, self._handle_total_count_loaded, done))

    def _handle_total_count_loaded(self, future) -> None:
        self.count_loading = False
        try:
            count = future.result()
        except Exception:
            count = None
        if count is None:
            self.set_status(f"已載入 {len(self.videos)} 部影片 / 頻道影片總數：未知。")
            return
        self.total_count = count
        self.set_status(f"已載入 {len(self.videos)} 部影片 / 頻道影片總數：約 {count:,} 部。")

    def _render_video_row(self, row_index: int, video: Video) -> None:
        frame = ctk.CTkFrame(self.video_list)
        frame.grid(row=row_index, column=0, sticky="ew", padx=6, pady=6)
        frame.grid_columnconfigure(2, weight=1)

        selectable = not video.is_downloaded
        var = ctk.BooleanVar(value=False)
        self.selected[video.youtube_video_id] = var
        checkbox = ctk.CTkCheckBox(frame, text="", variable=var, width=28)
        checkbox.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=10)
        if not selectable:
            checkbox.configure(state="disabled")

        thumbnail_label = ctk.CTkLabel(frame, image=self.default_thumbnail, text="")
        thumbnail_label.grid(row=0, column=1, rowspan=2, padx=6, pady=10)

        title = ctk.CTkLabel(frame, text=video.title, anchor="w", justify="left", wraplength=560, font=self.title_font)
        title.grid(row=0, column=2, sticky="ew", padx=8, pady=(10, 2))
        meta = self._video_meta(video)
        meta_label = ctk.CTkLabel(frame, text=meta, anchor="w", justify="left", font=self.font)
        meta_label.grid(
            row=1, column=2, sticky="ew", padx=8, pady=(2, 10)
        )

        status = ctk.CTkLabel(frame, text=self._status_text(video), width=130, anchor="e", font=self.font)
        status.grid(row=0, column=3, rowspan=2, sticky="e", padx=12, pady=10)
        self.rows[video.youtube_video_id] = {
            "status": status,
            "checkbox": checkbox,
            "thumbnail": thumbnail_label,
            "thumbnail_image": self.default_thumbnail,
            "meta": meta_label,
        }
        self._load_thumbnail_async(video)

    def _load_visible_video_details(self, videos: list[Video]) -> None:
        for video in videos:
            if video.youtube_video_id in self.details_requested:
                continue
            if video.upload_date and video.view_count is not None:
                continue
            self.details_requested.add(video.youtube_video_id)
            future = self.detail_executor.submit(self.youtube_service.get_video_details, video)
            future.add_done_callback(
                lambda done, video_id=video.youtube_video_id: self.after(
                    0, self._handle_video_details_loaded, video_id, done
                )
            )

    def _handle_video_details_loaded(self, video_id: str, future) -> None:
        try:
            detailed = future.result()
        except Exception:
            return
        self.videos = [
            detailed if video.youtube_video_id == video_id else video for video in self.videos
        ]
        self.filtered_videos = [
            detailed if video.youtube_video_id == video_id else video for video in self.filtered_videos
        ]
        row = self.rows.get(video_id)
        if row:
            row["meta"].configure(text=self._video_meta(detailed))
            row["status"].configure(text=self._status_text(detailed))

    def _load_thumbnail_async(self, video: Video) -> None:
        future = self.thumbnail_executor.submit(
            self.thumbnail_service.get_thumbnail,
            video.youtube_video_id,
            video.thumbnail_url,
        )
        future.add_done_callback(
            lambda done: self.after(0, partial(self._handle_thumbnail_loaded, video.youtube_video_id, done))
        )

    def _handle_thumbnail_loaded(self, video_id: str, future) -> None:
        row = self.rows.get(video_id)
        if row is None:
            return
        try:
            image = future.result()
        except Exception:
            image = None
        if image is None:
            return
        photo = ImageTk.PhotoImage(image)
        row["thumbnail_image"] = photo
        row["thumbnail"].configure(image=photo)

    def select_all(self) -> None:
        for video in self.filtered_videos:
            if not video.is_downloaded and video.youtube_video_id in self.selected:
                self.selected[video.youtube_video_id].set(True)

    def clear_selection(self) -> None:
        for var in self.selected.values():
            var.set(False)

    def download_selected(self) -> None:
        if self.selected_artist is None:
            self.set_status("請先選擇歌手。", error=True)
            return
        selected_ids = {
            video_id for video_id, var in self.selected.items() if var.get()
        }
        videos = [
            video for video in self.filtered_videos
            if video.youtube_video_id in selected_ids and not video.is_downloaded
        ]
        if not videos:
            self.set_status("沒有可下載的勾選影片。", error=True)
            return
        self.download_button.configure(state="disabled")
        self.set_status(f"開始批次下載 {len(videos)} 部影片...")
        future = self.worker_executor.submit(self._download_worker, self.selected_artist, videos)
        future.add_done_callback(lambda done: self.after(0, self._handle_download_finished, done))

    def _download_worker(self, artist: Artist, videos: list[Video]):
        success = 0
        failed = 0
        for video in videos:
            ok = self.download_service.download_video(artist, video, self._threadsafe_status)
            if ok:
                success += 1
            else:
                failed += 1
        return success, failed

    def _threadsafe_status(self, video_id: str, status: str) -> None:
        self.after(0, self._set_video_status, video_id, status)

    def _set_video_status(self, video_id: str, status: str) -> None:
        row = self.rows.get(video_id)
        if row:
            row["status"].configure(text=status)

    def _handle_download_finished(self, future) -> None:
        self.download_button.configure(state="normal")
        try:
            success, failed = future.result()
        except Exception as exc:
            self.set_status(f"批次下載失敗：{exc}", error=True)
            return
        self.set_status(f"批次完成：成功 {success}，失敗或略過 {failed}。")
        if self.selected_artist:
            self.videos = self.song_repository.mark_video_states(self.selected_artist.artist_id, self.videos)
            self.apply_filter()
        if self.on_downloads_changed:
            self.on_downloads_changed()

    def _video_meta(self, video: Video) -> str:
        duration = self._format_duration(video.duration)
        upload_date = self._format_upload_date(video.upload_date)
        view_count = self._format_view_count(video.view_count)
        return (
            f"ID: {video.youtube_video_id} | 長度: {duration} | 上傳: {upload_date} | 觀看: {view_count}\n"
            f"{video.youtube_url}"
        )

    def _status_text(self, video: Video) -> str:
        if video.file_missing:
            return "檔案遺失"
        if video.is_downloaded:
            return "已下載"
        return "未下載"

    def _format_duration(self, duration: int | None) -> str:
        if duration is None:
            return "未知"
        minutes, seconds = divmod(int(duration), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _format_upload_date(self, upload_date: str | None) -> str:
        if not upload_date:
            return "未知"
        if len(upload_date) == 8 and upload_date.isdigit():
            return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        return upload_date

    def _format_view_count(self, view_count: int | None) -> str:
        if view_count is None:
            return "未知"
        return f"{view_count:,}"

    def _artist_label(self, artist: Artist) -> str:
        return f"{artist.artist_id} - {artist.channel_name}"

    def _make_default_thumbnail(self):
        image = Image.new("RGB", THUMBNAIL_SIZE, "#d9dee8")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, THUMBNAIL_SIZE[0] - 1, THUMBNAIL_SIZE[1] - 1), outline="#8d96a8")
        draw.text((44, 36), "No Image", fill="#4a5568")
        return ImageTk.PhotoImage(image)

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def destroy(self) -> None:
        self.worker_executor.shutdown(wait=False, cancel_futures=True)
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        self.detail_executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
