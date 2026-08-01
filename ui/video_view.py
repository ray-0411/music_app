from concurrent.futures import ThreadPoolExecutor
from functools import partial
from random import uniform
from time import sleep

import customtkinter as ctk
from PIL import Image, ImageDraw

from config import APP_FONT_FAMILY, THUMBNAIL_SIZE, THUMBNAIL_WORKERS, VIDEO_BATCH_SIZE, VIDEO_PAGE_SIZE
from database.artist_repository import ArtistRepository
from database.song_repository import SongRepository
from database.video_stats_repository import VideoStatsRepository
from models.artist import Artist
from models.video import Video
from services.download_service import DownloadService
from services.thumbnail_service import ThumbnailService
from services.youtube_service import YouTubeService
from ui.fonts import base_font, button_font, small_title_font


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
        video_stats_repository: VideoStatsRepository,
        on_downloads_changed=None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.song_repository = song_repository
        self.youtube_service = youtube_service
        self.thumbnail_service = thumbnail_service
        self.download_service = download_service
        self.video_stats_repository = video_stats_repository
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
        self.stats_update_loading = False
        self.video_load_token = 0
        self.selected: dict[str, ctk.BooleanVar] = {}
        self.selected_video_ids: set[str] = set()
        self.rows: dict[str, dict] = {}
        self.details_requested: set[str] = set()
        self.sort_mode = ctk.StringVar(value="最新")
        self.default_thumbnail = self._make_default_thumbnail()
        self.is_destroyed = False
        self.font = base_font()
        self.button_font = button_font()
        self.title_font = small_title_font()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        toolbar.grid_columnconfigure(1, weight=1)
        toolbar.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(toolbar, text="歌手", font=self.font).grid(row=0, column=0, padx=(12, 6), pady=12)
        self.artist_menu = ctk.CTkOptionMenu(toolbar, values=["尚無歌手"], command=self._artist_selected, font=self.font)
        self.artist_menu.grid(row=0, column=1, sticky="ew", padx=6, pady=12)

        self.refresh_button = ctk.CTkButton(toolbar, text="取得 / 重新整理影片", command=self.load_videos, font=self.button_font)
        self.refresh_button.grid(row=0, column=2, padx=6, pady=12)

        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="搜尋影片標題", font=self.font)
        self.search_entry.grid(row=0, column=3, sticky="ew", padx=6, pady=12)
        self.search_entry.bind("<Return>", lambda _event: self.apply_filter())
        self.search_button = ctk.CTkButton(toolbar, text="搜尋", width=84, command=self.apply_filter, font=self.button_font)
        self.search_button.grid(row=0, column=4, padx=(0, 12), pady=12)

        actions = ctk.CTkFrame(self)
        actions.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.select_all_button = ctk.CTkButton(actions, text="全選", width=88, command=self.select_all, font=self.button_font)
        self.select_all_button.pack(side="left", padx=(12, 6), pady=10)
        self.clear_button = ctk.CTkButton(actions, text="取消全選", width=88, command=self.clear_selection, font=self.button_font)
        self.clear_button.pack(side="left", padx=6, pady=10)
        self.sort_menu = ctk.CTkOptionMenu(
            actions,
            values=["最新", "熱門"],
            variable=self.sort_mode,
            command=lambda _value: self.load_videos(),
            font=self.font,
            width=130,
        )
        self.sort_menu.pack(side="left", padx=6, pady=10)
        self.prev_button = ctk.CTkButton(actions, text="上一頁", width=88, command=self.prev_page, font=self.button_font)
        self.prev_button.pack(side="left", padx=6, pady=10)
        self.next_button = ctk.CTkButton(actions, text="下一頁", width=88, command=self.next_page, font=self.button_font)
        self.next_button.pack(side="left", padx=6, pady=10)
        self.page_label = ctk.CTkLabel(actions, text="第 0 / 0 頁", font=self.font)
        self.page_label.pack(side="left", padx=6, pady=10)
        self.selected_count_label = ctk.CTkLabel(actions, text="已選 0 首", font=self.font)
        self.selected_count_label.pack(side="left", padx=12, pady=10)
        self.download_button = ctk.CTkButton(actions, text="批次下載", width=120, command=self.download_selected, font=self.button_font)
        self.download_button.pack(side="right", padx=(6, 12), pady=10)
        self.video_list = ctk.CTkScrollableFrame(self)
        self.video_list.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.video_list.grid_columnconfigure(0, weight=1)

        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        status_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(status_frame, text="進度", anchor="w", font=self.font).grid(
            row=0, column=0, sticky="w", padx=(12, 8), pady=10
        )
        self.status_label = ctk.CTkLabel(status_frame, text="", anchor="w", font=self.font)
        self.status_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=10)

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
        self._clear_selection_state()

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
        self.stats_update_loading = False
        self._clear_selection_state()
        self.details_requested.clear()
        self.video_load_token += 1
        load_token = self.video_load_token
        self.render_videos()
        popular_sort = self._is_popular_sort()
        if popular_sort:
            self.set_status("正在取得完整影片清單，準備用觀看數排序...")
        else:
            self.set_status(f"正在取得前 {VIDEO_BATCH_SIZE} 部影片（最新）...")
        future = self.worker_executor.submit(
            self._load_videos_worker, self.selected_artist, 0, popular_sort
        )
        future.add_done_callback(lambda done: self._safe_after(self._handle_videos_loaded, done, False, load_token))

    def _load_videos_worker(self, artist: Artist, start: int, popular_sort: bool):
        limit = None if popular_sort else VIDEO_BATCH_SIZE
        result = self.youtube_service.list_channel_videos(
            artist.youtube_url, start=start, limit=limit
        )
        self.video_stats_repository.save_view_counts(result.videos)
        videos = self.video_stats_repository.apply_cached_view_counts(result.videos)
        videos = self.song_repository.mark_video_states(artist.artist_id, videos)
        return result, videos

    def _is_popular_sort(self) -> bool:
        return self.sort_mode.get() == "熱門"

    def _start_background_view_count_update(self) -> None:
        if self.stats_update_loading or not self.videos:
            return
        self.stats_update_loading = True
        load_token = self.video_load_token
        videos = list(self.videos)
        future = self.worker_executor.submit(self._update_view_counts_worker, videos, load_token)
        future.add_done_callback(lambda done: self._safe_after(self._handle_view_counts_updated, done, load_token))

    def _update_view_counts_worker(self, videos: list[Video], load_token: int) -> tuple[list[Video], int]:
        if not videos:
            return [], 0
        stale_ids = self.video_stats_repository.stale_video_ids(videos)
        if not stale_ids:
            self._safe_after(
                self._set_status_for_token,
                load_token,
                f"觀看數快取仍在 7 天內，已使用快取排序 {len(videos)} 部影片。",
            )
            return [], 0
        detailed_videos: list[Video] = []
        total = len(stale_ids)
        self._safe_after(self._set_status_for_token, load_token, f"正在更新觀看數：0/{total}（0%）")
        stale_videos = [video for video in videos if video.youtube_video_id in stale_ids]
        for completed, video in enumerate(stale_videos, start=1):
            if load_token != self.video_load_token:
                return detailed_videos, total
            try:
                detailed = self.youtube_service.get_video_details(video)
            except Exception:
                detailed = None
            if detailed and detailed.view_count == -1:
                self.video_stats_repository.mark_view_count_unavailable(video.youtube_video_id)
            elif detailed and detailed.view_count is not None:
                updated_video = Video(
                    youtube_video_id=video.youtube_video_id,
                    youtube_url=video.youtube_url,
                    title=video.title,
                    thumbnail_url=video.thumbnail_url,
                    duration=video.duration,
                    upload_date=video.upload_date,
                    view_count=detailed.view_count,
                    download_status=video.download_status,
                    is_downloaded=video.is_downloaded,
                    file_missing=video.file_missing,
                )
                detailed_videos.append(updated_video)
                self.video_stats_repository.save_view_count(video.youtube_video_id, detailed.view_count)
            else:
                self.video_stats_repository.mark_view_count_failed(video.youtube_video_id)
            percent = int(completed * 100 / total)
            self._safe_after(
                self._set_status_for_token,
                load_token,
                f"正在更新觀看數：{completed}/{total}（{percent}%）",
            )
            if completed < total:
                sleep(uniform(0.35, 0.9))
        return detailed_videos, total

    def _handle_view_counts_updated(self, future, load_token: int) -> None:
        self.stats_update_loading = False
        if load_token != self.video_load_token:
            return
        try:
            detailed_videos, total = future.result()
        except Exception as exc:
            self.set_status(f"觀看數背景更新失敗：{exc}", error=True)
            return
        if not detailed_videos or not self._is_popular_sort():
            return
        detailed_by_id = {video.youtube_video_id: video for video in detailed_videos}
        self.videos = [
            detailed_by_id.get(video.youtube_video_id, video)
            for video in self.videos
        ]
        self.videos.sort(
            key=self._view_count_sort_key,
            reverse=True,
        )
        self.apply_filter()
        self.set_status(f"觀看數背景更新完成：{len(detailed_videos)}/{total}，已重新排序。")

    def _handle_videos_loaded(self, future, append: bool, load_token: int) -> None:
        self.refresh_button.configure(state="normal")
        self.loading_more = False
        if load_token != self.video_load_token:
            return
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
        if self._is_popular_sort():
            self.videos.sort(
                key=self._view_count_sort_key,
                reverse=True,
            )
        if result.total_count is not None:
            self.total_count = result.total_count
        elif self._is_popular_sort():
            self.total_count = len(self.videos)
        self.has_more = result.limited
        self.apply_filter()
        total_text = f" / 頻道共約 {self.total_count} 部" if self.total_count else ""
        if self.total_count is None:
            total_text = " / 頻道影片總數：未知"
        notice = f"已載入 {len(self.videos)} 部影片{total_text}。"
        if self.has_more:
            notice += " 接近最後一頁時會自動載入下一批。"
        self.set_status(notice)
        if self._is_popular_sort() and not append:
            self._start_background_view_count_update()
        if not append and not self._is_popular_sort():
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
        self._scroll_video_list_to_top()
        self.rows.clear()
        self.selected.clear()
        self._sync_selected_ids_with_available_videos()
        self._update_selected_count()
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

    def _scroll_video_list_to_top(self) -> None:
        try:
            self.video_list._parent_canvas.yview_moveto(0)
        except Exception:
            pass

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
        if self._is_popular_sort():
            return
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
        popular_sort = self._is_popular_sort()
        if popular_sort:
            self.set_status(f"正在載入第 {start + 1} 到 {start + VIDEO_BATCH_SIZE} 部影片，並補齊觀看數排序...")
        else:
            self.set_status(f"正在載入第 {start + 1} 到 {start + VIDEO_BATCH_SIZE} 部影片...")
        future = self.worker_executor.submit(
            self._load_videos_worker, self.selected_artist, start, popular_sort
        )
        future.add_done_callback(
            lambda done, load_token=self.video_load_token: self._safe_after(
                self._handle_videos_loaded, done, True, load_token
            )
        )

    def _load_total_count_async(self) -> None:
        if self.selected_artist is None or self.count_loading:
            return
        self.count_loading = True
        artist = self.selected_artist
        future = self.worker_executor.submit(
            self.youtube_service.count_channel_videos, artist.youtube_url
        )
        future.add_done_callback(lambda done: self._safe_after(self._handle_total_count_loaded, done))

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
        frame.grid(row=row_index, column=0, sticky="ew", padx=6, pady=3)
        frame.grid_propagate(False)
        frame.configure(height=112)
        frame.grid_columnconfigure(2, weight=1)

        selectable = not video.is_downloaded
        var = ctk.BooleanVar(
            value=video.is_downloaded or video.youtube_video_id in self.selected_video_ids
        )
        self.selected[video.youtube_video_id] = var
        checkbox = ctk.CTkCheckBox(
            frame,
            text="",
            variable=var,
            width=28,
            command=lambda video_id=video.youtube_video_id, selected_var=var: self._selection_changed(
                video_id, selected_var
            ),
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=5)
        if not selectable:
            checkbox.configure(
                state="disabled",
                fg_color="#8a8f98",
                border_color="#8a8f98",
                checkmark_color="#f4f7f2",
            )

        thumbnail_label = ctk.CTkLabel(frame, image=self.default_thumbnail, text="")
        thumbnail_label.grid(row=0, column=1, rowspan=2, padx=6, pady=5)

        title = ctk.CTkLabel(
            frame,
            text=self._two_line_title(video.title),
            anchor="w",
            justify="left",
            wraplength=820,
            font=self.title_font,
        )
        title.grid(row=0, column=2, sticky="ew", padx=8, pady=(5, 1))
        meta = self._video_meta(video)
        meta_label = ctk.CTkLabel(frame, text=meta, anchor="w", justify="left", font=self.font)
        meta_label.grid(
            row=1, column=2, sticky="ew", padx=8, pady=(1, 5)
        )

        status = ctk.CTkLabel(frame, text=self._status_text(video), width=96, anchor="e", font=self.font)
        status.grid(row=0, column=3, rowspan=2, sticky="e", padx=(8, 10), pady=5)
        self.rows[video.youtube_video_id] = {
            "status": status,
            "checkbox": checkbox,
            "thumbnail": thumbnail_label,
            "thumbnail_image": self.default_thumbnail,
            "meta": meta_label,
        }
        self._load_thumbnail_async(video)

    def _two_line_title(self, title: str) -> str:
        cleaned = " ".join(title.split())
        max_chars = 78
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 1].rstrip() + "…"

    def _load_visible_video_details(self, videos: list[Video]) -> None:
        if self._is_popular_sort():
            return
        stale_ids = self.video_stats_repository.stale_video_ids(videos)
        for video in videos:
            if video.youtube_video_id in self.details_requested:
                continue
            if video.upload_date and video.view_count is not None and video.youtube_video_id not in stale_ids:
                continue
            self.details_requested.add(video.youtube_video_id)
            future = self.detail_executor.submit(self.youtube_service.get_video_details, video)
            future.add_done_callback(
                lambda done, video_id=video.youtube_video_id: self._safe_after(
                    self._handle_video_details_loaded, video_id, done
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
        self.video_stats_repository.save_view_count(video_id, detailed.view_count)
        if self._is_popular_sort():
            self.videos.sort(
                key=self._view_count_sort_key,
                reverse=True,
            )
            self.apply_filter()
            return
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
            lambda done: self._safe_after(
                partial(self._handle_thumbnail_loaded, video.youtube_video_id, done)
            )
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
        photo = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=self._fit_image_size(image.size, THUMBNAIL_SIZE),
        )
        row["thumbnail_image"] = photo
        row["thumbnail"].configure(image=photo)

    def _selection_changed(self, video_id: str, selected_var: ctk.BooleanVar) -> None:
        if selected_var.get():
            self.selected_video_ids.add(video_id)
        else:
            self.selected_video_ids.discard(video_id)
        self._update_selected_count()

    def _sync_selected_ids_with_available_videos(self) -> None:
        downloadable_ids = {
            video.youtube_video_id for video in self.videos if not video.is_downloaded
        }
        self.selected_video_ids.intersection_update(downloadable_ids)

    def _update_selected_count(self) -> None:
        if not hasattr(self, "selected_count_label"):
            return
        self.selected_count_label.configure(text=f"已選 {len(self.selected_video_ids)} 首")

    def select_all(self) -> None:
        for video in self.filtered_videos:
            if not video.is_downloaded:
                self.selected_video_ids.add(video.youtube_video_id)
                if video.youtube_video_id in self.selected:
                    self.selected[video.youtube_video_id].set(True)
        self._update_selected_count()

    def clear_selection(self) -> None:
        self._clear_selection_state()
        for var in self.selected.values():
            var.set(False)

    def _clear_selection_state(self) -> None:
        self.selected_video_ids.clear()
        self._update_selected_count()

    def download_selected(self) -> None:
        if self.selected_artist is None:
            self.set_status("請先選擇歌手。", error=True)
            return
        selected_ids = set(self.selected_video_ids)
        videos = [
            video for video in self.videos
            if video.youtube_video_id in selected_ids and not video.is_downloaded
        ]
        if not videos:
            self.set_status("沒有可下載的勾選影片。", error=True)
            return
        self.download_button.configure(state="disabled")
        self.set_status(f"下載進度：0/{len(videos)}")
        future = self.worker_executor.submit(self._download_worker, self.selected_artist, videos)
        future.add_done_callback(lambda done: self._safe_after(self._handle_download_finished, done))

    def _download_worker(self, artist: Artist, videos: list[Video]):
        success = 0
        failed = 0
        total = len(videos)
        for index, video in enumerate(videos, start=1):
            self._threadsafe_status(video.youtube_video_id, f"下載進度：{index - 1}/{total}，處理中")
            ok = self.download_service.download_video(artist, video, self._threadsafe_status)
            if ok:
                success += 1
            else:
                failed += 1
            self._safe_after(self.set_status, f"下載進度：{index}/{total}")
        return success, failed

    def _threadsafe_status(self, video_id: str, status: str) -> None:
        self._safe_after(self._set_video_status, video_id, status)

    def _set_video_status(self, video_id: str, status: str) -> None:
        row = self.rows.get(video_id)
        if row:
            row["status"].configure(text=status)
        if status.startswith("下載進度："):
            self.set_status(status)

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
            self.selected_video_ids.difference_update(
                video.youtube_video_id for video in self.videos if video.is_downloaded
            )
            self._update_selected_count()
            self.apply_filter()
        if self.on_downloads_changed:
            self.on_downloads_changed()

    def _video_meta(self, video: Video) -> str:
        duration = self._format_duration(video.duration)
        upload_date = self._format_upload_date(video.upload_date)
        view_count = self._format_view_count(video.view_count)
        return f"長度: {duration} | 上傳: {upload_date} | 觀看: {view_count}"

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
        if view_count == -1:
            return "不可抓"
        return f"{view_count:,}"

    def _view_count_sort_key(self, video: Video) -> int:
        if video.view_count is None or video.view_count < 0:
            return -1
        return video.view_count

    def _artist_label(self, artist: Artist) -> str:
        return f"{artist.artist_id} - {artist.channel_name}"

    def _make_default_thumbnail(self):
        image = Image.new("RGB", THUMBNAIL_SIZE, "#d9dee8")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, THUMBNAIL_SIZE[0] - 1, THUMBNAIL_SIZE[1] - 1), outline="#8d96a8")
        draw.text((44, 36), "No Image", fill="#4a5568")
        return ctk.CTkImage(light_image=image, dark_image=image, size=THUMBNAIL_SIZE)

    def _fit_image_size(self, image_size: tuple[int, int], max_size: tuple[int, int]) -> tuple[int, int]:
        width, height = image_size
        max_width, max_height = max_size
        if width <= 0 or height <= 0:
            return max_size
        scale = min(max_width / width, max_height / height)
        return (max(1, int(width * scale)), max(1, int(height * scale)))

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def _set_status_for_token(self, load_token: int, text: str, *, error: bool = False) -> None:
        if load_token == self.video_load_token:
            self.set_status(text, error=error)

    def destroy(self) -> None:
        self.is_destroyed = True
        self.worker_executor.shutdown(wait=False, cancel_futures=True)
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        self.detail_executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()

    def _safe_after(self, callback, *args) -> None:
        if self.is_destroyed:
            return
        try:
            self.after(0, callback, *args)
        except Exception:
            return
