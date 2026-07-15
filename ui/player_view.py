import customtkinter as ctk
from PIL import Image, ImageDraw

from config import PLAYER_COVER_SIZE
from database.artist_repository import ArtistRepository
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
        playback_service: PlaybackService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.song_repository = song_repository
        self.artist_repository = artist_repository
        self.playback_service = playback_service
        self.thumbnail_service = thumbnail_service
        self.artist_names: dict[str, str] = {}
        self.playlist: list[Song] = []
        self.cover_images: dict[str, ctk.CTkImage] = {}
        self.default_cover_image = self._make_default_cover()
        self.is_dragging_slider = False
        self.progress_after_id: str | None = None
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
        self.previous_label = self._make_queue_label("上一首", 1)
        self.current_label = self._make_queue_label("本首", 2)
        self.next_label = self._make_queue_label("下一首", 3)

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
        ctk.CTkLabel(self.rating_frame, text="評分功能預留", anchor="nw", font=self.font).grid(
            row=1, column=0, sticky="nsew", padx=14, pady=8
        )

        self.status_label = ctk.CTkLabel(self.center_frame, text="", anchor="w", font=self.font)
        self.status_label.grid(row=7, column=0, sticky="ew", padx=18, pady=(0, 12))

    def _build_preference_page(self) -> None:
        ctk.CTkLabel(
            self.preference_page,
            text="標籤偏好設定",
            anchor="w",
            font=self.title_font,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 8))
        filter_frame = ctk.CTkFrame(self.preference_page)
        filter_frame.grid(row=1, column=0, sticky="nsew", padx=(18, 8), pady=(8, 18))
        filter_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(filter_frame, text="篩選標籤", anchor="w", font=self.section_font).grid(
            row=0, column=0, sticky="ew", padx=14, pady=(14, 8)
        )
        ctk.CTkLabel(filter_frame, text="只播放符合某些標籤的歌曲。功能預留。", anchor="nw", font=self.font).grid(
            row=1, column=0, sticky="nsew", padx=14, pady=8
        )

        weight_frame = ctk.CTkFrame(self.preference_page)
        weight_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 18), pady=(8, 18))
        weight_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(weight_frame, text="加權標籤", anchor="w", font=self.section_font).grid(
            row=0, column=0, sticky="ew", padx=14, pady=(14, 8)
        )
        ctk.CTkLabel(weight_frame, text="提高某些標籤歌曲出現機率。功能預留。", anchor="nw", font=self.font).grid(
            row=1, column=0, sticky="nsew", padx=14, pady=8
        )

    def show_play_page(self) -> None:
        self.preference_page.grid_remove()
        self.play_page.grid()

    def show_preference_page(self) -> None:
        self.play_page.grid_remove()
        self.preference_page.grid()

    def _make_queue_label(self, title: str, row: int) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            self.queue_frame,
            text=f"{title}\n-",
            anchor="w",
            justify="left",
            wraplength=230,
            font=self.font,
        )
        label.grid(row=row, column=0, sticky="ew", padx=14, pady=8)
        return label

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
        self.previous_label.configure(text=f"上一首\n{self._song_label(previous_song)}")
        self.current_label.configure(text=f"本首\n{self._song_label(current_song)}")
        self.next_label.configure(text=f"下一首\n{self._song_label(next_song)}")
        if current_song is None:
            self.now_title_label.configure(text="尚未播放")
            self.now_artist_label.configure(text="")
            self.cover_label.configure(image=self.default_cover_image)
            return
        self.now_title_label.configure(text=self._display_song_name(current_song))
        self.now_artist_label.configure(text=self._artist_name(current_song))
        self._refresh_cover(current_song)

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

    def _artist_name(self, song: Song) -> str:
        return self.artist_names.get(song.artist_id.lower(), song.artist_id)

    def _display_song_name(self, song: Song) -> str:
        return build_song_name(song.artist_id, song.song_name)

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
