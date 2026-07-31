import customtkinter as ctk
from PIL import Image, ImageDraw

from config import PLAYER_COVER_SIZE
from database.artist_repository import ArtistRepository
from database.rating_repository import RatingRepository
from database.song_repository import SongRepository
from models.song import Song
from services.playback_service import PlaybackService
from services.thumbnail_service import ThumbnailService
from ui.fonts import base_font, button_font, small_title_font, title_font
from utils.filename import build_song_name


class PlayerView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        song_repository: SongRepository,
        artist_repository: ArtistRepository,
        rating_repository: RatingRepository,
        playback_service: PlaybackService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.song_repository = song_repository
        self.artist_repository = artist_repository
        self.rating_repository = rating_repository
        self.playback_service = playback_service
        self.thumbnail_service = thumbnail_service
        self.artist_names: dict[str, str] = {}
        self.playlist: list[Song] = []
        self.cover_images: dict[str, ctk.CTkImage] = {}
        self.default_cover_image = self._make_default_cover()
        self.is_dragging_slider = False
        self.progress_after_id: str | None = None
        self.rating_score_var = ctk.IntVar(value=5)
        self.rating_type_var = ctk.StringVar(value="影響演算法")
        self.artist_rating_score_var = ctk.IntVar(value=5)
        self.artist_rating_type_var = ctk.StringVar(value="影響演算法")
        self.play_order_var = ctk.StringVar(value="照順序")
        self.random_mode_var = ctk.StringVar(value="相同機率")
        self.current_rating_song_id: int | None = None
        self.song_rating_submitted_for_current_play = False
        self.artist_rating_submitted_for_current_play = False
        self.font = base_font()
        self.button_font = button_font()
        self.title_font = title_font()
        self.section_font = small_title_font()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.play_page = ctk.CTkFrame(self, fg_color="transparent")
        self.play_page.grid(row=0, column=0, sticky="nsew")
        self.play_page.grid_columnconfigure(0, weight=1, minsize=280, uniform="player_columns")
        self.play_page.grid_columnconfigure(1, weight=2, minsize=420, uniform="player_columns")
        self.play_page.grid_columnconfigure(2, weight=1, minsize=260, uniform="player_columns")
        self.play_page.grid_rowconfigure(0, weight=1)

        self.preference_page = ctk.CTkFrame(self, fg_color="transparent")
        self.preference_page.grid(row=0, column=0, sticky="nsew")
        self.preference_page.grid_columnconfigure((0, 1), weight=1)
        self.preference_page.grid_rowconfigure(1, weight=1)

        self._build_play_page()
        self._build_preference_page()
        self.show_play_page()
        self.reload_playlist()
        self._schedule_progress_update()

    def _build_play_page(self) -> None:
        self.queue_frame = ctk.CTkFrame(self.play_page)
        self.queue_frame.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=8)
        self.queue_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.queue_frame, text="播放資訊", anchor="w", font=self.title_font).grid(
            row=0, column=0, sticky="ew", padx=14, pady=(14, 10)
        )
        self.previous_queue = self._make_queue_item("上一首", 1)
        self.current_queue = self._make_queue_item("本首", 2)
        self.next_queue = self._make_queue_item("下一首", 3)
        self.mechanism_label = ctk.CTkLabel(
            self.queue_frame,
            text="目前機制\n-",
            anchor="sw",
            justify="left",
            wraplength=230,
            font=self.font,
        )
        self.mechanism_label.grid(row=4, column=0, sticky="sew", padx=14, pady=(18, 14))
        self.queue_frame.grid_rowconfigure(4, weight=1)

        self.center_frame = ctk.CTkFrame(self.play_page)
        self.center_frame.grid(row=0, column=1, sticky="nsew", padx=6, pady=8)
        self.center_frame.grid_columnconfigure(0, weight=1)
        self.center_frame.grid_rowconfigure(6, weight=1)

        self.cover_label = ctk.CTkLabel(self.center_frame, image=self.default_cover_image, text="")
        self.cover_label.grid(row=0, column=0, pady=(26, 16))

        self.now_title_label = ctk.CTkLabel(
            self.center_frame,
            text="尚未播放",
            anchor="center",
            font=self.title_font,
            wraplength=520,
        )
        self.now_title_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.now_artist_label = ctk.CTkLabel(
            self.center_frame,
            text="",
            anchor="center",
            font=self.section_font,
        )
        self.now_artist_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))

        progress_frame = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        progress_frame.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        progress_frame.grid_columnconfigure(1, weight=1)
        self.current_time_label = ctk.CTkLabel(progress_frame, text="0:00", width=56, font=self.font)
        self.current_time_label.grid(row=0, column=0, padx=(0, 8))
        self.progress_slider = ctk.CTkSlider(progress_frame, from_=0, to=1000, command=self._slider_changed)
        self.progress_slider.grid(row=0, column=1, sticky="ew")
        self.progress_slider.set(0)
        self.progress_slider.bind("<ButtonPress-1>", lambda _event: self._start_slider_drag())
        self.progress_slider.bind("<ButtonRelease-1>", lambda _event: self._finish_slider_drag())
        self.total_time_label = ctk.CTkLabel(progress_frame, text="0:00", width=56, font=self.font)
        self.total_time_label.grid(row=0, column=2, padx=(8, 0))

        controls = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        controls.grid(row=4, column=0, pady=(0, 18))
        self.prev_button = ctk.CTkButton(
            controls,
            text="⏮",
            width=72,
            command=self.play_previous,
            font=self.button_font,
        )
        self.prev_button.pack(side="left", padx=8)
        self.play_button = ctk.CTkButton(
            controls,
            text="▶",
            width=88,
            command=self.toggle_play_pause,
            font=self.button_font,
        )
        self.play_button.pack(side="left", padx=8)
        self.next_button = ctk.CTkButton(
            controls,
            text="⏭",
            width=72,
            command=self.play_next,
            font=self.button_font,
        )
        self.next_button.pack(side="left", padx=8)

        volume_frame = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        volume_frame.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 18))
        volume_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(volume_frame, text="音量", width=56, anchor="w", font=self.font).grid(
            row=0, column=0, padx=(0, 8)
        )
        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, command=self.set_volume)
        self.volume_slider.grid(row=0, column=1, sticky="ew")
        self.volume_slider.set(self.playback_service.get_volume())
        self.volume_label = ctk.CTkLabel(
            volume_frame,
            text=f"{self.playback_service.get_volume()}%",
            width=56,
            font=self.font,
        )
        self.volume_label.grid(row=0, column=2, padx=(8, 0))

        self.rating_frame = ctk.CTkFrame(self.play_page)
        self.rating_frame.grid(row=0, column=2, sticky="nsew", padx=(6, 8), pady=8)
        self.rating_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.rating_frame, text="評分區", anchor="w", font=self.title_font).grid(
            row=0, column=0, sticky="ew", padx=14, pady=(14, 8)
        )
        ctk.CTkLabel(self.rating_frame, text="歌曲評分", anchor="w", font=self.section_font).grid(
            row=1, column=0, sticky="ew", padx=14, pady=(4, 6)
        )
        self.rating_song_label = ctk.CTkLabel(
            self.rating_frame,
            text="目前沒有歌曲",
            anchor="w",
            justify="left",
            wraplength=220,
            font=self.font,
        )
        self.rating_song_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.rating_value_label = ctk.CTkLabel(self.rating_frame, text="5 / 10", font=self.section_font)
        self.rating_value_label.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 4))
        ctk.CTkSlider(
            self.rating_frame,
            from_=0,
            to=10,
            number_of_steps=10,
            variable=self.rating_score_var,
            command=lambda value: self._update_rating_label(value),
        ).grid(row=4, column=0, sticky="ew", padx=14, pady=4)
        ctk.CTkOptionMenu(
            self.rating_frame,
            values=["影響演算法", "單純評分"],
            variable=self.rating_type_var,
            font=self.font,
        ).grid(row=5, column=0, sticky="ew", padx=14, pady=6)
        self.submit_rating_button = ctk.CTkButton(
            self.rating_frame,
            text="送出評分",
            command=self.submit_current_song_rating,
            font=self.button_font,
            state="disabled",
        )
        self.submit_rating_button.grid(row=6, column=0, sticky="ew", padx=14, pady=(6, 8))
        self.rating_status_label = ctk.CTkLabel(
            self.rating_frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=220,
            font=self.font,
        )
        self.rating_status_label.grid(row=7, column=0, sticky="ew", padx=14, pady=(0, 12))

        ctk.CTkLabel(self.rating_frame, text="歌手評分", anchor="w", font=self.section_font).grid(
            row=8, column=0, sticky="ew", padx=14, pady=(8, 6)
        )
        self.artist_rating_song_label = ctk.CTkLabel(
            self.rating_frame,
            text="目前沒有歌手",
            anchor="w",
            justify="left",
            wraplength=220,
            font=self.font,
        )
        self.artist_rating_song_label.grid(row=9, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.artist_rating_value_label = ctk.CTkLabel(self.rating_frame, text="5 / 10", font=self.section_font)
        self.artist_rating_value_label.grid(row=10, column=0, sticky="ew", padx=14, pady=(0, 4))
        ctk.CTkSlider(
            self.rating_frame,
            from_=0,
            to=10,
            number_of_steps=10,
            variable=self.artist_rating_score_var,
            command=lambda value: self._update_artist_rating_label(value),
        ).grid(row=11, column=0, sticky="ew", padx=14, pady=4)
        ctk.CTkOptionMenu(
            self.rating_frame,
            values=["影響演算法", "單純評分"],
            variable=self.artist_rating_type_var,
            font=self.font,
        ).grid(row=12, column=0, sticky="ew", padx=14, pady=6)
        self.submit_artist_rating_button = ctk.CTkButton(
            self.rating_frame,
            text="送出歌手評分",
            command=self.submit_current_artist_rating,
            font=self.button_font,
            state="disabled",
        )
        self.submit_artist_rating_button.grid(row=13, column=0, sticky="ew", padx=14, pady=(6, 8))
        self.artist_rating_status_label = ctk.CTkLabel(
            self.rating_frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=220,
            font=self.font,
        )
        self.artist_rating_status_label.grid(row=14, column=0, sticky="ew", padx=14, pady=(0, 12))

        self.status_label = ctk.CTkLabel(self.center_frame, text="", anchor="w", font=self.font)
        self.status_label.grid(row=7, column=0, sticky="ew", padx=18, pady=(0, 12))

    def _build_preference_page(self) -> None:
        ctk.CTkLabel(
            self.preference_page,
            text="播放設定",
            anchor="w",
            font=self.title_font,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 8))

        playback_frame = ctk.CTkFrame(self.preference_page)
        playback_frame.grid(row=1, column=0, sticky="nsew", padx=(18, 8), pady=(8, 18))
        playback_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(playback_frame, text="下一首規則", anchor="w", font=self.section_font).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(14, 10)
        )
        ctk.CTkLabel(playback_frame, text="播放順序", anchor="w", font=self.font).grid(
            row=1, column=0, sticky="w", padx=14, pady=8
        )
        self.play_order_menu = ctk.CTkOptionMenu(
            playback_frame,
            values=["照順序", "隨機"],
            variable=self.play_order_var,
            command=lambda _value: self._sync_random_controls_state(),
            font=self.font,
        )
        self.play_order_menu.grid(row=1, column=1, sticky="ew", padx=14, pady=8)
        ctk.CTkLabel(playback_frame, text="隨機方式", anchor="w", font=self.font).grid(
            row=2, column=0, sticky="w", padx=14, pady=8
        )
        self.random_mode_menu = ctk.CTkOptionMenu(
            playback_frame,
            values=["相同機率", "評分權重"],
            variable=self.random_mode_var,
            font=self.font,
        )
        self.random_mode_menu.grid(row=2, column=1, sticky="ew", padx=14, pady=8)
        ctk.CTkLabel(playback_frame, text="同曲間隔", anchor="w", font=self.font).grid(
            row=3, column=0, sticky="w", padx=14, pady=8
        )
        self.repeat_gap_entry = ctk.CTkEntry(playback_frame, font=self.font)
        self.repeat_gap_entry.grid(row=3, column=1, sticky="ew", padx=14, pady=8)
        button_row = ctk.CTkFrame(playback_frame, fg_color="transparent")
        button_row.grid(row=4, column=1, sticky="w", padx=14, pady=(14, 8))
        ctk.CTkButton(
            button_row,
            text="開始",
            command=self.start_with_playback_settings,
            font=self.button_font,
            width=92,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            button_row,
            text="儲存設定",
            command=self.save_playback_settings_only,
            font=self.button_font,
            width=112,
        ).pack(side="left")
        self.playback_setting_status_label = ctk.CTkLabel(
            playback_frame,
            text="",
            anchor="w",
            font=self.font,
        )
        self.playback_setting_status_label.grid(row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))

        weight_frame = ctk.CTkFrame(self.preference_page)
        weight_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 18), pady=(8, 18))
        weight_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(weight_frame, text="標籤規則", anchor="w", font=self.section_font).grid(
            row=0, column=0, sticky="ew", padx=14, pady=(14, 8)
        )
        ctk.CTkLabel(weight_frame, text="標籤篩選與標籤加權功能預留。", anchor="nw", font=self.font).grid(
            row=1, column=0, sticky="nsew", padx=14, pady=8
        )
        self._load_playback_settings_into_controls()

    def show_play_page(self) -> None:
        self.preference_page.grid_remove()
        self.play_page.grid()

    def show_preference_page(self) -> None:
        self.play_page.grid_remove()
        self._load_playback_settings_into_controls()
        self.preference_page.grid()

    def _load_playback_settings_into_controls(self) -> None:
        self.play_order_var.set("隨機" if self.playback_service.get_play_order() == "random" else "照順序")
        self.random_mode_var.set("評分權重" if self.playback_service.get_random_mode() == "rating" else "相同機率")
        if hasattr(self, "repeat_gap_entry"):
            self.repeat_gap_entry.delete(0, "end")
            self.repeat_gap_entry.insert(0, str(self.playback_service.get_repeat_gap()))
        self._sync_random_controls_state()

    def start_with_playback_settings(self) -> None:
        try:
            play_order, random_mode, repeat_gap = self._selected_playback_settings()
        except ValueError as exc:
            self.playback_setting_status_label.configure(text=str(exc), text_color="#b3261e")
            return
        try:
            self.playback_service.save_playback_settings(
                play_order=play_order,
                random_mode=random_mode,
                repeat_gap=repeat_gap,
                reset_next=True,
            )
            started = self.playback_service.restart_with_current_settings(autoplay=False)
        except Exception as exc:
            self.playback_setting_status_label.configure(text=str(exc), text_color="#b3261e")
            return
        if not started:
            self.playback_setting_status_label.configure(text="沒有可播放的 MP3。", text_color="#b3261e")
            return
        self.play_button.configure(text="▶")
        self.playback_setting_status_label.configure(text="已套用設定並重新開始。", text_color="#1b6e3c")
        self._sync_random_controls_state()
        self._refresh_song_labels()

    def save_playback_settings_only(self) -> None:
        try:
            play_order, random_mode, repeat_gap = self._selected_playback_settings()
        except ValueError as exc:
            self.playback_setting_status_label.configure(text=str(exc), text_color="#b3261e")
            return
        try:
            self.playback_service.save_playback_settings(
                play_order=play_order,
                random_mode=random_mode,
                repeat_gap=repeat_gap,
                reset_next=False,
            )
        except Exception as exc:
            self.playback_setting_status_label.configure(text=str(exc), text_color="#b3261e")
            return
        self.playback_setting_status_label.configure(text="已儲存設定，從之後抽歌開始套用。", text_color="#1b6e3c")
        self._sync_random_controls_state()
        self._refresh_song_labels()

    def _selected_playback_settings(self) -> tuple[str, str, int]:
        try:
            repeat_gap = int(self.repeat_gap_entry.get().strip())
            if repeat_gap < 0:
                raise ValueError
        except ValueError:
            raise ValueError("同曲間隔必須是 0 或正整數。")
        play_order = "random" if self.play_order_var.get() == "隨機" else "sequential"
        random_mode = "rating" if self.random_mode_var.get() == "評分權重" else "equal"
        return play_order, random_mode, repeat_gap

    def _mechanism_text(self) -> str:
        if self.playback_service.get_play_order() == "sequential":
            return "照順序播放"
        random_mode = "評分權重" if self.playback_service.get_random_mode() == "rating" else "相同機率"
        repeat_gap = self.playback_service.get_repeat_gap()
        gap_text = "不限制同曲重複" if repeat_gap == 0 else f"同曲間隔至少 {repeat_gap} 首"
        return f"隨機 / {random_mode}\n{gap_text}"

    def _sync_random_controls_state(self) -> None:
        if not hasattr(self, "random_mode_menu"):
            return
        self.random_mode_menu.configure(state="normal" if self.play_order_var.get() == "隨機" else "disabled")

    def _make_queue_item(self, title: str, row: int) -> dict[str, ctk.CTkLabel]:
        frame = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=14, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(frame, text=title, anchor="w", font=self.font)
        title_label.grid(row=0, column=0, sticky="ew")
        song_label = ctk.CTkLabel(
            frame,
            text="-",
            anchor="w",
            justify="left",
            wraplength=230,
            font=self.section_font,
        )
        song_label.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        artist_label = ctk.CTkLabel(
            frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=230,
            font=self.font,
        )
        artist_label.grid(row=2, column=0, sticky="ew", pady=(2, 0))
        return {"song": song_label, "artist": artist_label}

    def reload_playlist(self) -> None:
        self.artist_names = {
            artist.artist_id.lower(): artist.channel_name
            for artist in self.artist_repository.list_artists()
        }
        self.playlist = self.song_repository.list_songs()
        self.playback_service.load_playlist(self.playlist)
        self._refresh_song_labels()
        if not self.playback_service.available:
            self.set_status("找不到 VLC。請安裝 VLC 桌面版，並執行 pip install python-vlc。", error=True)
        elif not self.playback_service.current_song():
            self.set_status("沒有可播放的 MP3。")
        else:
            self.set_status(f"已載入 {len(self.playback_service.songs)} 首歌曲。")

    def refresh_display(self) -> None:
        self.artist_names = {
            artist.artist_id.lower(): artist.channel_name
            for artist in self.artist_repository.list_artists()
        }
        self._refresh_song_labels()

    def toggle_play_pause(self) -> None:
        try:
            is_playing = self.playback_service.toggle_play_pause()
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.play_button.configure(text="⏸" if is_playing else "▶")
        self._refresh_song_labels()

    def play_previous(self) -> None:
        was_playing = self.playback_service.is_playing()
        try:
            moved = self.playback_service.play_previous(autoplay=was_playing)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        if not moved:
            self.set_status("已經是第一首。", error=True)
            return
        self.play_button.configure(text="⏸" if was_playing else "▶")
        self._refresh_song_labels()

    def play_next(self) -> None:
        was_playing = self.playback_service.is_playing()
        try:
            moved = self.playback_service.play_next(autoplay=was_playing)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        if not moved:
            self.set_status("已經是最後一首。", error=True)
            return
        self.play_button.configure(text="⏸" if was_playing else "▶")
        self._refresh_song_labels()

    def set_volume(self, value: float) -> None:
        volume = int(value)
        try:
            self.playback_service.set_volume(volume)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.volume_label.configure(text=f"{volume}%")

    def _refresh_song_labels(self) -> None:
        previous_song = self.playback_service.previous_song()
        current_song = self.playback_service.current_song()
        next_song = self.playback_service.next_song()
        self.prev_button.configure(state="normal" if previous_song else "disabled")
        self.next_button.configure(state="normal" if next_song else "disabled")
        self._update_queue_item(self.previous_queue, previous_song)
        self._update_queue_item(self.current_queue, current_song)
        self._update_queue_item(self.next_queue, next_song)
        self.mechanism_label.configure(text=f"目前機制\n{self._mechanism_text()}")
        if current_song is None:
            self.now_title_label.configure(text="尚未播放")
            self.now_artist_label.configure(text="")
            self.cover_label.configure(image=self.default_cover_image)
            self._refresh_rating_panel(None)
            return
        self.now_title_label.configure(text=self._display_song_name(current_song))
        self.now_artist_label.configure(text=self._artist_name(current_song))
        self._refresh_cover(current_song)
        self._refresh_rating_panel(current_song)

    def _refresh_cover(self, song: Song) -> None:
        if song.youtube_video_id in self.cover_images:
            self.cover_label.configure(image=self.cover_images[song.youtube_video_id])
            return
        image = self.thumbnail_service.get_existing_song_cover(song.youtube_video_id)
        if image is None:
            self.cover_label.configure(image=self.default_cover_image)
            return
        image = self._crop_letterbox(image.copy())
        display_size = self._fit_cover_size(image.size)
        cover = ctk.CTkImage(light_image=image, dark_image=image, size=display_size)
        self.cover_images[song.youtube_video_id] = cover
        self.cover_label.configure(image=cover)

    def _song_label(self, song: Song | None) -> str:
        if song is None:
            return "-"
        return f"{self._artist_name(song)}\n{self._display_song_name(song)}"

    def _update_queue_item(self, item: dict[str, ctk.CTkLabel], song: Song | None) -> None:
        if song is None:
            item["song"].configure(text="-")
            item["artist"].configure(text="")
            return
        item["song"].configure(text=self._display_song_name(song))
        item["artist"].configure(text=self._artist_name(song))

    def _artist_name(self, song: Song) -> str:
        return self.artist_names.get(song.artist_id.lower(), song.artist_id)

    def _display_song_name(self, song: Song) -> str:
        return build_song_name(song.artist_id, song.song_name)

    def _refresh_rating_panel(self, song: Song | None) -> None:
        if song is None or song.id is None:
            self.current_rating_song_id = None
            self.song_rating_submitted_for_current_play = False
            self.artist_rating_submitted_for_current_play = False
            self._reset_rating_controls()
            self.rating_song_label.configure(text="目前沒有歌曲")
            self.rating_status_label.configure(text="")
            self.submit_rating_button.configure(state="disabled")
            self.artist_rating_song_label.configure(text="目前沒有歌手")
            self.artist_rating_status_label.configure(text="")
            self.submit_artist_rating_button.configure(state="disabled")
            return
        if song.id != self.current_rating_song_id:
            self.current_rating_song_id = song.id
            self.song_rating_submitted_for_current_play = False
            self.artist_rating_submitted_for_current_play = False
            self._reset_rating_controls()
        self.rating_song_label.configure(text=self._display_song_name(song))
        self.rating_status_label.configure(text=self._song_rating_status_text(song))
        self.submit_rating_button.configure(state=self._song_rating_button_state(song))
        self.artist_rating_song_label.configure(text=f"{self._artist_name(song)}\n{song.artist_id}")
        self.artist_rating_status_label.configure(text=self._artist_rating_status_text(song.artist_id))
        self.submit_artist_rating_button.configure(state=self._artist_rating_button_state(song.artist_id))

    def submit_current_song_rating(self) -> None:
        song = self.playback_service.current_song()
        if song is None or song.id is None:
            self.set_status("目前沒有可評分的歌曲。", error=True)
            return
        score = int(round(self.rating_score_var.get()))
        affects_algorithm = self.rating_type_var.get() == "影響演算法"
        try:
            self.rating_repository.add_song_rating(
                song.id,
                score,
                affects_algorithm=affects_algorithm,
                enforce_daily_limit=False,
            )
        except Exception as exc:
            self.set_status(str(exc), error=True)
            self.rating_status_label.configure(text=self._song_rating_status_text(song))
            self.submit_rating_button.configure(state=self._song_rating_button_state(song))
            return
        self.song_rating_submitted_for_current_play = True
        self.rating_status_label.configure(text=self._song_rating_status_text(song))
        self.submit_rating_button.configure(state="disabled")
        self.set_status(f"已送出歌曲評分：{score}/10")

    def submit_current_artist_rating(self) -> None:
        song = self.playback_service.current_song()
        if song is None:
            self.set_status("目前沒有可評分的歌手。", error=True)
            return
        score = int(round(self.artist_rating_score_var.get()))
        affects_algorithm = self.artist_rating_type_var.get() == "影響演算法"
        try:
            self.rating_repository.add_artist_rating(
                song.artist_id,
                score,
                affects_algorithm=affects_algorithm,
                enforce_daily_limit=False,
            )
        except Exception as exc:
            self.set_status(str(exc), error=True)
            self.artist_rating_status_label.configure(text=self._artist_rating_status_text(song.artist_id))
            self.submit_artist_rating_button.configure(state=self._artist_rating_button_state(song.artist_id))
            return
        self.artist_rating_submitted_for_current_play = True
        self.artist_rating_status_label.configure(text=self._artist_rating_status_text(song.artist_id))
        self.submit_artist_rating_button.configure(state="disabled")
        self.set_status(f"已送出歌手評分：{score}/10")

    def _song_rating_status_text(self, song: Song) -> str:
        if song.id is None:
            return "尚未記錄評分"
        count = self.rating_repository.song_rating_count(song.id)
        return f"已記錄 {count} 筆評分"

    def _artist_rating_status_text(self, artist_id: str) -> str:
        count = self.rating_repository.artist_rating_count(artist_id)
        return f"已記錄 {count} 筆評分"

    def _song_rating_button_state(self, song: Song) -> str:
        if song.id is None:
            return "disabled"
        if self.song_rating_submitted_for_current_play:
            return "disabled"
        return "normal"

    def _artist_rating_button_state(self, artist_id: str) -> str:
        if self.artist_rating_submitted_for_current_play:
            return "disabled"
        return "normal"

    def _reset_rating_controls(self) -> None:
        self.rating_score_var.set(5)
        self.rating_type_var.set("影響演算法")
        self.rating_value_label.configure(text="5 / 10")
        self.artist_rating_score_var.set(5)
        self.artist_rating_type_var.set("影響演算法")
        self.artist_rating_value_label.configure(text="5 / 10")

    def _update_rating_label(self, value) -> None:
        score = int(round(float(value)))
        self.rating_score_var.set(score)
        self.rating_value_label.configure(text=f"{score} / 10")

    def _update_artist_rating_label(self, value) -> None:
        score = int(round(float(value)))
        self.artist_rating_score_var.set(score)
        self.artist_rating_value_label.configure(text=f"{score} / 10")

    def _start_slider_drag(self) -> None:
        self.is_dragging_slider = True

    def _finish_slider_drag(self) -> None:
        self.is_dragging_slider = False
        try:
            self.playback_service.seek_ms(int(self.progress_slider.get()))
        except Exception as exc:
            self.set_status(str(exc), error=True)

    def _slider_changed(self, value: float) -> None:
        if self.is_dragging_slider:
            self.current_time_label.configure(text=self._format_time_ms(int(value)))

    def _schedule_progress_update(self) -> None:
        self._update_progress()
        self.progress_after_id = self.after(500, self._schedule_progress_update)

    def _update_progress(self) -> None:
        if self.playback_service.is_ended():
            if self.playback_service.play_next():
                self.play_button.configure(text="⏸")
                self._refresh_song_labels()
            else:
                self.play_button.configure(text="▶")
        length_ms = self.playback_service.get_length_ms()
        time_ms = self.playback_service.get_time_ms()
        if length_ms > 0:
            self.progress_slider.configure(to=length_ms)
            self.total_time_label.configure(text=self._format_time_ms(length_ms))
            if not self.is_dragging_slider:
                self.progress_slider.set(time_ms)
                self.current_time_label.configure(text=self._format_time_ms(time_ms))
        else:
            self.total_time_label.configure(text="0:00")
            if not self.is_dragging_slider:
                self.progress_slider.set(0)
                self.current_time_label.configure(text="0:00")

    def _format_time_ms(self, time_ms: int) -> str:
        total_seconds = max(int(time_ms / 1000), 0)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def _make_default_cover(self) -> ctk.CTkImage:
        image = Image.new("RGB", PLAYER_COVER_SIZE, "#d9dee8")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, PLAYER_COVER_SIZE[0] - 1, PLAYER_COVER_SIZE[1] - 1), outline="#8d96a8")
        draw.text((122, 78), "No Image", fill="#4a5568")
        return ctk.CTkImage(light_image=image, dark_image=image, size=PLAYER_COVER_SIZE)

    def _fit_cover_size(self, image_size: tuple[int, int]) -> tuple[int, int]:
        width, height = image_size
        max_width, max_height = PLAYER_COVER_SIZE
        if width <= 0 or height <= 0:
            return PLAYER_COVER_SIZE
        scale = min(max_width / width, max_height / height)
        return (max(1, int(width * scale)), max(1, int(height * scale)))

    def _crop_letterbox(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        pixels = image.load()

        def row_is_black(row: int) -> bool:
            sample_count = 0
            dark_count = 0
            step = max(width // 50, 1)
            for x in range(0, width, step):
                red, green, blue = pixels[x, row][:3]
                sample_count += 1
                if red < 18 and green < 18 and blue < 18:
                    dark_count += 1
            return sample_count > 0 and dark_count / sample_count > 0.92

        top = 0
        while top < height // 3 and row_is_black(top):
            top += 1

        bottom = height - 1
        while bottom > height * 2 // 3 and row_is_black(bottom):
            bottom -= 1

        if top == 0 and bottom == height - 1:
            return image
        if bottom <= top:
            return image
        return image.crop((0, top, width, bottom + 1))

    def destroy(self) -> None:
        if self.progress_after_id is not None:
            try:
                self.after_cancel(self.progress_after_id)
            except Exception:
                pass
        super().destroy()
