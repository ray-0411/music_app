import re
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from config import APP_FONT_FAMILY, CHANNEL_AVATAR_SIZE
from database.artist_repository import ArtistRepository
from database.rating_repository import RatingRepository
from database.tag_repository import TagRepository
from models.artist import Artist
from services.thumbnail_service import ThumbnailService
from services.youtube_service import ChannelInfo
from services.youtube_service import YouTubeService
from ui.fonts import base_font, button_font, large_title_font, small_title_font, title_font
from change_artist_id import apply_change, build_change_plan

ARTIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
ARTIST_CARD_COLUMNS = 3
ARTIST_PAGE_SIZE = 12
BULK_LIST_COLUMNS = 3
BULK_LIST_ROWS = 12
BULK_LIST_PAGE_SIZE = BULK_LIST_COLUMNS * BULK_LIST_ROWS
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
        rating_repository: RatingRepository,
        on_artists_changed,
        on_artist_id_change_start=None,
        on_artist_id_change_finished=None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.youtube_service = youtube_service
        self.thumbnail_service = thumbnail_service
        self.tag_repository = tag_repository
        self.rating_repository = rating_repository
        self.on_artists_changed = on_artists_changed
        self.on_artist_id_change_start = on_artist_id_change_start
        self.on_artist_id_change_finished = on_artist_id_change_finished
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.channel_name_entries: dict[str, ctk.CTkEntry] = {}
        self.tag_vars: dict[int, ctk.BooleanVar] = {}
        self.artist_avatar_labels: dict[str, ctk.CTkLabel] = {}
        self.artist_avatar_images: dict[str, ctk.CTkImage] = {}
        self.avatar_requests: set[str] = set()
        self.editing_artist_id: str | None = None
        self.preview_channel: ChannelInfo | None = None
        self.editing_artist: Artist | None = None
        self.all_artists: list[Artist] = []
        self.artists: list[Artist] = []
        self.current_artist_page = 0
        self.artist_search_keyword = ""
        self.selected_artist_search_tag_id: int | None = None
        self.artist_search_tag_labels: dict[str, int | None] = {"全部分類": None, "無": -1}
        self.artist_search_category_option_ids: set[int] = set()
        self.bulk_tag_labels: dict[str, int] = {}
        self.bulk_tag_vars: dict[str, ctk.BooleanVar] = {}
        self.selected_bulk_tag_id: int | None = None
        self.selected_bulk_category_name = ""
        self.bulk_tag_artists: list[Artist] = []
        self.current_bulk_tag_page = 0
        self.bulk_avatar_labels: dict[str, ctk.CTkLabel] = {}
        self.bulk_list_mode_var = ctk.BooleanVar(value=False)
        self.default_avatar_image = self._make_default_avatar()
        self.preview_avatar_image = self._make_default_avatar()
        self.artist_rating_score_var = ctk.IntVar(value=5)
        self.artist_rating_type_var = ctk.StringVar(value="影響演算法")
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
        self.list_page.grid_rowconfigure(0, weight=0)
        self.list_page.grid_rowconfigure(1, weight=1)
        self.list_page.grid_rowconfigure(2, weight=0)

        self.edit_page = ctk.CTkScrollableFrame(self)
        self.edit_page.grid(row=0, column=0, sticky="nsew")
        self.edit_page.grid_columnconfigure(1, weight=1)
        self.edit_page.grid_columnconfigure(2, weight=0, minsize=260)

        self.bulk_tag_page = ctk.CTkFrame(self, fg_color="transparent")
        self.bulk_tag_page.grid(row=0, column=0, sticky="nsew")
        self.bulk_tag_page.grid_columnconfigure(0, weight=1)
        self.bulk_tag_page.grid_rowconfigure(1, weight=1)

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

        self.artist_search_frame = ctk.CTkFrame(self.list_page)
        self.artist_search_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.artist_search_frame.grid_columnconfigure(0, weight=1)
        self.artist_search_frame.grid_columnconfigure(1, weight=1)
        self.artist_search_tag_menu = ctk.CTkOptionMenu(
            self.artist_search_frame,
            values=list(self.artist_search_tag_labels.keys()),
            font=self.font,
        )
        self.artist_search_tag_menu.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=10)
        self.artist_search_entry = ctk.CTkEntry(self.artist_search_frame, placeholder_text="歌手名稱或 Artist ID", font=self.font)
        self.artist_search_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=10)
        self.artist_search_entry.bind("<Return>", lambda _event: self.apply_artist_search())
        ctk.CTkButton(
            self.artist_search_frame,
            text="搜尋",
            width=84,
            command=self.apply_artist_search,
            font=self.button_font,
        ).grid(row=0, column=2, padx=6, pady=10)
        ctk.CTkButton(
            self.artist_search_frame,
            text="清除",
            width=84,
            command=self.clear_artist_search,
            font=self.button_font,
        ).grid(row=0, column=3, padx=(6, 12), pady=10)

        self.artist_list = ctk.CTkFrame(self.list_page, fg_color="transparent")
        self.artist_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.artist_list.grid_columnconfigure(0, weight=1)
        self.artist_pagination_frame = ctk.CTkFrame(self.list_page)
        self.artist_pagination_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
        self.artist_pagination_frame.grid_columnconfigure(1, weight=1)
        self.prev_artist_page_button = ctk.CTkButton(
            self.artist_pagination_frame,
            text="上一頁",
            width=96,
            command=self.previous_artist_page,
            font=self.button_font,
        )
        self.prev_artist_page_button.grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.artist_page_label = ctk.CTkLabel(self.artist_pagination_frame, text="", anchor="center", font=self.font)
        self.artist_page_label.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        self.next_artist_page_button = ctk.CTkButton(
            self.artist_pagination_frame,
            text="下一頁",
            width=96,
            command=self.next_artist_page,
            font=self.button_font,
        )
        self.next_artist_page_button.grid(row=0, column=2, sticky="e", padx=10, pady=8)
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
        self.bulk_tag_page.grid_remove()
        self.add_page.grid()

    def show_list_page(self) -> None:
        self.reload_artists()
        self.edit_page.grid_remove()
        self.add_page.grid_remove()
        self.bulk_tag_page.grid_remove()
        self.list_page.grid()

    def show_edit_page(self, artist: Artist) -> None:
        self.editing_artist = artist
        self.render_edit_page()
        self.add_page.grid_remove()
        self.list_page.grid_remove()
        self.bulk_tag_page.grid_remove()
        self.edit_page.grid()

    def show_bulk_tag_page(self) -> None:
        self.render_bulk_tag_page()
        self.edit_page.grid_remove()
        self.add_page.grid_remove()
        self.list_page.grid_remove()
        self.bulk_tag_page.grid()

    def reload_artists(self) -> None:
        for child in self.artist_list.winfo_children():
            child.destroy()
        self.channel_name_entries.clear()
        self.artist_avatar_labels.clear()
        self._reload_artist_search_tag_labels()
        self.all_artists = self.artist_repository.list_artists()
        self.artists = self._filter_artists(self.all_artists)
        max_page = self._max_artist_page()
        if self.current_artist_page > max_page:
            self.current_artist_page = max_page
        if not self.artists:
            empty_text = "找不到符合條件的歌手" if self.all_artists else "尚未新增歌手"
            ctk.CTkLabel(self.artist_list, text=empty_text, anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            self._update_artist_pagination_controls()
            return
        for column in range(ARTIST_CARD_COLUMNS):
            self.artist_list.grid_columnconfigure(column, weight=1, uniform="artist_cards")
        start = self.current_artist_page * ARTIST_PAGE_SIZE
        end = start + ARTIST_PAGE_SIZE
        for index, artist in enumerate(self.artists[start:end]):
            row = index // ARTIST_CARD_COLUMNS
            column = index % ARTIST_CARD_COLUMNS
            frame = ctk.CTkFrame(self.artist_list)
            frame.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            frame.configure(width=ARTIST_CARD_WIDTH, height=ARTIST_CARD_HEIGHT)
            frame.grid_propagate(False)
            frame.grid_columnconfigure(1, weight=1)
            frame.grid_rowconfigure(0, weight=1)

            avatar_label = ctk.CTkLabel(frame, image=self.default_avatar_image, text="")
            avatar_label.grid(row=0, column=0, padx=(10, 8), pady=10)
            self.artist_avatar_labels[artist.artist_id] = avatar_label
            if artist.artist_id in self.artist_avatar_images:
                avatar_label.configure(image=self.artist_avatar_images[artist.artist_id])
            else:
                image = self.thumbnail_service.get_existing_channel_avatar(artist.channel_id)
                if image is not None:
                    photo = ctk.CTkImage(light_image=image, dark_image=image, size=CHANNEL_AVATAR_SIZE)
                    self.artist_avatar_images[artist.artist_id] = photo
                    avatar_label.configure(image=photo)
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
        self._update_artist_pagination_controls()

    def previous_artist_page(self) -> None:
        if self.current_artist_page <= 0:
            return
        self.current_artist_page -= 1
        self.reload_artists()

    def next_artist_page(self) -> None:
        if self.current_artist_page >= self._max_artist_page():
            return
        self.current_artist_page += 1
        self.reload_artists()

    def _max_artist_page(self) -> int:
        if not self.artists:
            return 0
        return (len(self.artists) - 1) // ARTIST_PAGE_SIZE

    def _update_artist_pagination_controls(self) -> None:
        if not self.artists:
            self.artist_page_label.configure(text="第 0 / 0 頁")
            self.prev_artist_page_button.configure(state="disabled")
            self.next_artist_page_button.configure(state="disabled")
            return
        total_pages = self._max_artist_page() + 1
        start = self.current_artist_page * ARTIST_PAGE_SIZE + 1
        end = min(start + ARTIST_PAGE_SIZE - 1, len(self.artists))
        self.artist_page_label.configure(
            text=f"第 {self.current_artist_page + 1} / {total_pages} 頁，顯示 {start}-{end} / {len(self.artists)}"
        )
        self.prev_artist_page_button.configure(state="normal" if self.current_artist_page > 0 else "disabled")
        self.next_artist_page_button.configure(
            state="normal" if self.current_artist_page < self._max_artist_page() else "disabled"
        )

    def apply_artist_search(self) -> None:
        self.artist_search_keyword = self.artist_search_entry.get().strip()
        self.selected_artist_search_tag_id = self.artist_search_tag_labels.get(self.artist_search_tag_menu.get())
        self.current_artist_page = 0
        self.reload_artists()

    def clear_artist_search(self) -> None:
        self.artist_search_keyword = ""
        self.selected_artist_search_tag_id = None
        self.artist_search_entry.delete(0, "end")
        self.artist_search_tag_menu.set("全部分類")
        self.current_artist_page = 0
        self.reload_artists()

    def _filter_artists(self, artists: list[Artist]) -> list[Artist]:
        keyword = self.artist_search_keyword.strip().lower()
        tag_id = self.selected_artist_search_tag_id
        if not keyword and tag_id is None:
            return list(artists)
        filtered: list[Artist] = []
        for artist in artists:
            if keyword and not self._artist_matches_keyword(artist, keyword):
                continue
            artist_option_ids = self.tag_repository.get_artist_option_ids(artist.artist_id) if tag_id is not None else set()
            if tag_id == -1 and self.artist_search_category_option_ids.intersection(artist_option_ids):
                continue
            if tag_id is not None and tag_id != -1 and tag_id not in artist_option_ids:
                continue
            filtered.append(artist)
        return filtered

    def _artist_matches_keyword(self, artist: Artist, keyword: str) -> bool:
        return keyword in artist.artist_id.lower() or keyword in artist.channel_name.lower()

    def _reload_artist_search_tag_labels(self) -> None:
        labels: dict[str, int | None] = {"全部分類": None, "無": -1}
        category_option_ids: set[int] = set()
        for category in self.tag_repository.list_categories():
            if category.name != "搜尋分類":
                continue
            for option in self.tag_repository.list_options_by_category(category.id):
                labels[option.name] = option.id
                category_option_ids.add(option.id)
        self.artist_search_tag_labels = labels
        self.artist_search_category_option_ids = category_option_ids
        if not hasattr(self, "artist_search_tag_menu"):
            return
        self.artist_search_tag_menu.configure(values=list(labels.keys()))
        current_label = self._artist_search_tag_label_by_id(self.selected_artist_search_tag_id)
        self.artist_search_tag_menu.set(current_label)

    def _artist_search_tag_label_by_id(self, option_id: int | None) -> str:
        if option_id is None:
            return "全部分類"
        for label, current_id in self.artist_search_tag_labels.items():
            if current_id == option_id:
                return label
        self.selected_artist_search_tag_id = None
        return "全部分類"

    def render_bulk_tag_page(self) -> None:
        for child in self.bulk_tag_page.winfo_children():
            child.destroy()
        self.bulk_tag_vars.clear()
        self.bulk_avatar_labels.clear()
        self.bulk_tag_categories = self.tag_repository.list_categories()

        controls = ctk.CTkFrame(self.bulk_tag_page)
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)
        controls.grid_columnconfigure(3, weight=1)
        category_labels = [category.name for category in self.bulk_tag_categories] or ["尚無上層標籤"]
        self.bulk_category_menu = ctk.CTkOptionMenu(
            controls,
            values=category_labels,
            command=self._bulk_category_selected,
            font=self.font,
        )
        self.bulk_category_menu.set(self._bulk_category_label())
        self.bulk_category_menu.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=10)
        self.bulk_tag_labels = self._bulk_option_labels_for_selected_category()
        option_values = list(self.bulk_tag_labels.keys()) or ["尚無下層標籤"]
        self.bulk_tag_menu = ctk.CTkOptionMenu(
            controls,
            values=option_values,
            command=self._bulk_tag_selected,
            font=self.font,
        )
        self.bulk_tag_menu.set(self._bulk_tag_label_by_id(self.selected_bulk_tag_id, option_values[0]))
        self.bulk_tag_menu.grid(row=0, column=1, sticky="ew", padx=6, pady=10)
        ctk.CTkButton(
            controls,
            text="儲存",
            width=96,
            command=self.save_bulk_artist_tags,
            font=self.button_font,
        ).grid(row=0, column=2, padx=6, pady=10)
        self.bulk_tag_status_label = ctk.CTkLabel(controls, text="", anchor="w", font=self.font)
        self.bulk_tag_status_label.grid(row=0, column=3, sticky="ew", padx=(6, 12), pady=10)
        ctk.CTkCheckBox(
            controls,
            text="清單模式",
            variable=self.bulk_list_mode_var,
            command=self.render_bulk_artist_cards,
            font=self.font,
        ).grid(row=0, column=4, sticky="e", padx=(6, 12), pady=10)

        body_shell = ctk.CTkFrame(self.bulk_tag_page, fg_color="transparent")
        body_shell.grid(row=1, column=0, sticky="nsew")
        body_shell.grid_columnconfigure(0, weight=1)
        body_shell.grid_rowconfigure(0, weight=1)
        self.bulk_tag_body = ctk.CTkFrame(body_shell, fg_color="transparent")
        self.bulk_tag_body.grid(row=0, column=0, sticky="nsew", padx=8, pady=(0, 4))
        for column in range(ARTIST_CARD_COLUMNS):
            self.bulk_tag_body.grid_columnconfigure(column, weight=1, uniform="bulk_artist_cards")
        self.bulk_pagination_frame = ctk.CTkFrame(body_shell)
        self.bulk_pagination_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 8))
        self.bulk_pagination_frame.grid_columnconfigure(1, weight=1)
        self.prev_bulk_page_button = ctk.CTkButton(
            self.bulk_pagination_frame,
            text="上一頁",
            width=96,
            command=self.previous_bulk_tag_page,
            font=self.button_font,
        )
        self.prev_bulk_page_button.grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.bulk_page_label = ctk.CTkLabel(self.bulk_pagination_frame, text="", anchor="center", font=self.font)
        self.bulk_page_label.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        self.next_bulk_page_button = ctk.CTkButton(
            self.bulk_pagination_frame,
            text="下一頁",
            width=96,
            command=self.next_bulk_tag_page,
            font=self.button_font,
        )
        self.next_bulk_page_button.grid(row=0, column=2, sticky="e", padx=10, pady=8)
        if self.selected_bulk_tag_id is None and self.bulk_tag_labels:
            self.selected_bulk_tag_id = self.bulk_tag_labels.get(self.bulk_tag_menu.get())
        if self.selected_bulk_tag_id is not None:
            self._load_bulk_tag_artist_states(self.selected_bulk_tag_id)
        self.render_bulk_artist_cards()

    def save_bulk_artist_tags(self) -> None:
        option_id = self.selected_bulk_tag_id
        if option_id is None:
            self._set_bulk_tag_status("請先選擇可用的下層標籤。", error=True)
            return
        try:
            for artist_id, var in self.bulk_tag_vars.items():
                self.tag_repository.set_artist_tag(artist_id, option_id, bool(var.get()))
        except Exception as exc:
            self._set_bulk_tag_status(str(exc), error=True)
            return
        self._set_bulk_tag_status(f"已批量更新標籤：{self._bulk_tag_label_by_id(option_id, '')}")
        self.reload_artists()

    def confirm_bulk_artist_tag(self) -> None:
        option_id = self.bulk_tag_labels.get(self.bulk_tag_menu.get()) if hasattr(self, "bulk_tag_menu") else None
        if option_id is None:
            self._set_bulk_tag_status("請先選擇可用的下層標籤。", error=True)
            self.bulk_tag_artists = []
            self.bulk_tag_vars.clear()
            self.render_bulk_artist_cards()
            return
        self.selected_bulk_tag_id = option_id
        self.current_bulk_tag_page = 0
        self._load_bulk_tag_artist_states(option_id)
        self._set_bulk_tag_status("已載入")
        self.render_bulk_artist_cards()

    def _load_bulk_tag_artist_states(self, option_id: int) -> None:
        self.bulk_tag_artists = self.artist_repository.list_artists()
        self.bulk_tag_vars.clear()
        for artist in self.bulk_tag_artists:
            option_ids = self.tag_repository.get_artist_option_ids(artist.artist_id)
            self.bulk_tag_vars[artist.artist_id] = ctk.BooleanVar(value=option_id in option_ids)

    def render_bulk_artist_cards(self) -> None:
        if not hasattr(self, "bulk_tag_body"):
            return
        for child in self.bulk_tag_body.winfo_children():
            child.destroy()
        self.bulk_avatar_labels.clear()
        if self.selected_bulk_tag_id is None:
            ctk.CTkLabel(self.bulk_tag_body, text="請選擇可用的下層標籤。", anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", padx=12, pady=12
            )
            self._update_bulk_pagination_controls()
            return
        if not self.bulk_tag_artists:
            ctk.CTkLabel(self.bulk_tag_body, text="尚未新增歌手。", anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", padx=12, pady=12
            )
            self._update_bulk_pagination_controls()
            return
        max_page = self._max_bulk_tag_page()
        if self.current_bulk_tag_page > max_page:
            self.current_bulk_tag_page = max_page
        page_size = self._bulk_tag_page_size()
        start = self.current_bulk_tag_page * page_size
        end = start + page_size
        if self.bulk_list_mode_var.get():
            self._render_bulk_artist_list(self.bulk_tag_artists[start:end])
            self._update_bulk_pagination_controls()
            return
        for index, artist in enumerate(self.bulk_tag_artists[start:end]):
            row = index // ARTIST_CARD_COLUMNS
            column = index % ARTIST_CARD_COLUMNS
            frame = ctk.CTkFrame(self.bulk_tag_body)
            frame.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            frame.configure(width=ARTIST_CARD_WIDTH, height=ARTIST_CARD_HEIGHT)
            frame.grid_propagate(False)
            frame.grid_columnconfigure(2, weight=1)
            frame.grid_rowconfigure(0, weight=1)

            var = self.bulk_tag_vars.get(artist.artist_id)
            if var is None:
                var = ctk.BooleanVar(value=False)
                self.bulk_tag_vars[artist.artist_id] = var
            ctk.CTkCheckBox(frame, text="", variable=var, width=28).grid(
                row=0, column=0, padx=(10, 4), pady=10
            )

            avatar_label = ctk.CTkLabel(frame, image=self.default_avatar_image, text="")
            avatar_label.grid(row=0, column=1, padx=(4, 8), pady=10)
            self.bulk_avatar_labels[artist.artist_id] = avatar_label
            if artist.artist_id in self.artist_avatar_images:
                avatar_label.configure(image=self.artist_avatar_images[artist.artist_id])
            else:
                image = self.thumbnail_service.get_existing_channel_avatar(artist.channel_id)
                if image is not None:
                    photo = ctk.CTkImage(light_image=image, dark_image=image, size=CHANNEL_AVATAR_SIZE)
                    self.artist_avatar_images[artist.artist_id] = photo
                    avatar_label.configure(image=photo)
                else:
                    self._load_artist_avatar_async(artist)

            text_frame = ctk.CTkFrame(frame, fg_color="transparent")
            text_frame.grid(row=0, column=2, sticky="ew", padx=6, pady=10)
            text_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                text_frame,
                text=artist.channel_name,
                anchor="w",
                wraplength=ARTIST_CARD_TEXT_WIDTH,
                font=self.font,
            ).grid(row=0, column=0, sticky="ew")
            ctk.CTkLabel(
                text_frame,
                text=artist.artist_id,
                anchor="w",
                wraplength=ARTIST_CARD_TEXT_WIDTH,
                font=self.font,
            ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self._update_bulk_pagination_controls()

    def _render_bulk_artist_list(self, artists: list[Artist]) -> None:
        for column in range(BULK_LIST_COLUMNS):
            self.bulk_tag_body.grid_columnconfigure(column, weight=1, uniform="bulk_artist_list")
        for index, artist in enumerate(artists):
            var = self.bulk_tag_vars.get(artist.artist_id)
            if var is None:
                var = ctk.BooleanVar(value=False)
                self.bulk_tag_vars[artist.artist_id] = var
            row_frame = ctk.CTkFrame(self.bulk_tag_body)
            row_frame.grid(
                row=index % BULK_LIST_ROWS,
                column=index // BULK_LIST_ROWS,
                sticky="ew",
                padx=6,
                pady=3,
            )
            row_frame.grid_columnconfigure(2, weight=1)
            ctk.CTkCheckBox(row_frame, text="", variable=var, width=28).grid(
                row=0, column=0, padx=(10, 8), pady=8
            )
            ctk.CTkLabel(
                row_frame,
                text=self._artist_search_category_text(artist),
                width=96,
                anchor="w",
                font=self.font,
            ).grid(row=0, column=1, sticky="w", padx=8, pady=8)
            ctk.CTkLabel(
                row_frame,
                text=artist.channel_name,
                anchor="w",
                font=self.font,
            ).grid(row=0, column=2, sticky="ew", padx=8, pady=8)

    def _artist_search_category_text(self, artist: Artist) -> str:
        option_ids = self.tag_repository.get_artist_option_ids(artist.artist_id)
        names: list[str] = []
        for category in self.tag_repository.list_categories():
            if category.name != "搜尋分類":
                continue
            for option in self.tag_repository.list_options_by_category(category.id):
                if option.id in option_ids:
                    names.append(option.name)
        return "、".join(names) if names else "無"

    def previous_bulk_tag_page(self) -> None:
        if self.current_bulk_tag_page <= 0:
            return
        self.current_bulk_tag_page -= 1
        self.render_bulk_artist_cards()

    def next_bulk_tag_page(self) -> None:
        if self.current_bulk_tag_page >= self._max_bulk_tag_page():
            return
        self.current_bulk_tag_page += 1
        self.render_bulk_artist_cards()

    def _max_bulk_tag_page(self) -> int:
        if not self.bulk_tag_artists:
            return 0
        return (len(self.bulk_tag_artists) - 1) // self._bulk_tag_page_size()

    def _bulk_tag_page_size(self) -> int:
        return BULK_LIST_PAGE_SIZE if self.bulk_list_mode_var.get() else ARTIST_PAGE_SIZE

    def _update_bulk_pagination_controls(self) -> None:
        if not hasattr(self, "bulk_page_label"):
            return
        if not self.bulk_tag_artists:
            self.bulk_page_label.configure(text="第 0 / 0 頁")
            self.prev_bulk_page_button.configure(state="disabled")
            self.next_bulk_page_button.configure(state="disabled")
            return
        total_pages = self._max_bulk_tag_page() + 1
        page_size = self._bulk_tag_page_size()
        start = self.current_bulk_tag_page * page_size + 1
        end = min(start + page_size - 1, len(self.bulk_tag_artists))
        self.bulk_page_label.configure(
            text=f"第 {self.current_bulk_tag_page + 1} / {total_pages} 頁，顯示 {start}-{end} / {len(self.bulk_tag_artists)}"
        )
        self.prev_bulk_page_button.configure(state="normal" if self.current_bulk_tag_page > 0 else "disabled")
        self.next_bulk_page_button.configure(
            state="normal" if self.current_bulk_tag_page < self._max_bulk_tag_page() else "disabled"
        )

    def _bulk_category_selected(self, label: str) -> None:
        self.selected_bulk_category_name = label
        self.selected_bulk_tag_id = None
        self.render_bulk_tag_page()

    def _bulk_option_labels_for_selected_category(self) -> dict[str, int]:
        selected_category_name = self.bulk_category_menu.get() if hasattr(self, "bulk_category_menu") else ""
        labels: dict[str, int] = {}
        for category in self.bulk_tag_categories:
            if category.name != selected_category_name:
                continue
            for option in self.tag_repository.list_options_by_category(category.id):
                labels[option.name] = option.id
            break
        return labels

    def _bulk_category_label(self) -> str:
        if self.selected_bulk_category_name:
            for category in self.bulk_tag_categories:
                if category.name == self.selected_bulk_category_name:
                    return category.name
        if self.selected_bulk_tag_id is not None:
            for category in self.bulk_tag_categories:
                option_ids = {
                    option.id for option in self.tag_repository.list_options_by_category(category.id)
                }
                if self.selected_bulk_tag_id in option_ids:
                    return category.name
        return self.bulk_tag_categories[0].name if self.bulk_tag_categories else "尚無上層標籤"

    def _bulk_tag_selected(self, label: str) -> None:
        self.confirm_bulk_artist_tag()

    def _bulk_tag_label_by_id(self, option_id: int | None, fallback: str) -> str:
        if option_id is None:
            return fallback
        for label, current_id in self.bulk_tag_labels.items():
            if current_id == option_id:
                return label
        self.selected_bulk_tag_id = None
        if self.bulk_tag_labels:
            self.selected_bulk_tag_id = self.bulk_tag_labels.get(fallback)
        return fallback

    def _set_bulk_tag_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        if hasattr(self, "bulk_tag_status_label"):
            self.bulk_tag_status_label.configure(text=text, text_color=color)

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
        if label is not None:
            label.configure(image=photo)
        bulk_label = self.bulk_avatar_labels.get(artist_id)
        if bulk_label is not None:
            bulk_label.configure(image=photo)

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
            row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(self.edit_page, text="Artist ID", font=self.font).grid(
            row=1, column=0, sticky="w", padx=12, pady=8
        )
        artist_id_controls = ctk.CTkFrame(self.edit_page, fg_color="transparent")
        artist_id_controls.grid(row=1, column=1, sticky="ew", padx=12, pady=8)
        artist_id_controls.grid_columnconfigure(0, weight=1)
        self.edit_artist_id_entry = ctk.CTkEntry(artist_id_controls, font=self.font)
        self.edit_artist_id_entry.insert(0, artist.artist_id)
        self.edit_artist_id_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            artist_id_controls,
            text="修改 ID",
            width=112,
            font=self.button_font,
            command=self.change_artist_id_from_edit,
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        ctk.CTkLabel(self.edit_page, text="頻道名稱", font=self.font).grid(
            row=2, column=0, sticky="w", padx=12, pady=8
        )
        self.edit_channel_name_entry = ctk.CTkEntry(self.edit_page, font=self.font)
        self.edit_channel_name_entry.insert(0, artist.channel_name)
        self.edit_channel_name_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(self.edit_page, text="標籤", font=self.bold_font).grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(18, 8)
        )
        selected_option_ids = self.tag_repository.get_artist_option_ids(artist.artist_id)
        row = 4
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

        self._render_artist_rating_panel(artist, row)

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

    def _render_artist_rating_panel(self, artist: Artist, row_span: int) -> None:
        panel = ctk.CTkFrame(self.edit_page)
        panel.grid(row=1, column=2, rowspan=max(row_span, 4), sticky="new", padx=(16, 12), pady=8)
        panel.grid_columnconfigure(0, weight=1)
        self.artist_rating_score_var.set(5)
        self.artist_rating_type_var.set("影響演算法")
        ctk.CTkLabel(panel, text="歌手評分", anchor="w", font=self.font).grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 8)
        )
        self.artist_rating_value_label = ctk.CTkLabel(panel, text="5 / 10", font=self.font)
        self.artist_rating_value_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkSlider(
            panel,
            from_=0,
            to=10,
            number_of_steps=10,
            variable=self.artist_rating_score_var,
            command=lambda value: self._update_artist_rating_label(value),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        ctk.CTkOptionMenu(
            panel,
            values=["影響演算法", "單純評分"],
            variable=self.artist_rating_type_var,
            font=self.font,
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=8)
        self.artist_rating_submit_button = ctk.CTkButton(
            panel,
            text="送出評分",
            command=self.submit_artist_rating,
            font=self.button_font,
            state="disabled" if self.rating_repository.has_artist_rating_today(artist.artist_id) else "normal",
        )
        self.artist_rating_submit_button.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 12))
        self.artist_rating_status_label = ctk.CTkLabel(
            panel,
            text=self._artist_rating_status_text(artist.artist_id),
            anchor="w",
            font=self.font,
        )
        self.artist_rating_status_label.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

    def save_artist_edit(self) -> None:
        artist = self.editing_artist
        if artist is None:
            return
        try:
            old_artist_id = artist.artist_id
            new_artist_id = self.edit_artist_id_entry.get().strip()
            if old_artist_id.lower() != new_artist_id.lower():
                raise ValueError("修改 Artist ID 請使用旁邊的「修改 ID」按鈕。")
            updated = self.artist_repository.update_channel_name(
                artist.artist_id,
                self.edit_channel_name_entry.get(),
            )
            selected = {option_id for option_id, var in self.tag_vars.items() if var.get()}
            self.tag_repository.replace_artist_tags(updated.artist_id, selected)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.editing_artist = updated
        self.set_status(f"已更新歌手：{updated.artist_id} / {updated.channel_name}")
        self.on_artists_changed()
        self.show_list_page()

    def change_artist_id_from_edit(self) -> None:
        artist = self.editing_artist
        if artist is None:
            return
        old_artist_id = artist.artist_id
        new_artist_id = self.edit_artist_id_entry.get().strip()
        if old_artist_id.lower() == new_artist_id.lower():
            self.set_status("Artist ID 沒有變更。", error=True)
            return
        try:
            plan = build_change_plan(old_artist_id, new_artist_id)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return

        confirmed = messagebox.askyesno(
            "確認修改 Artist ID",
            f"確認把 {old_artist_id} 改成 {new_artist_id}？\n\n"
            f"會同步改名 {len(plan)} 首歌曲檔案。\n"
            "完成後程式會關閉，請手動重新開啟。",
        )
        if not confirmed:
            return

        try:
            if self.on_artist_id_change_start:
                self.on_artist_id_change_start()
            apply_change(old_artist_id, new_artist_id, plan)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return

        messagebox.showinfo(
            "Artist ID 已修改",
            f"{old_artist_id} 已改成 {new_artist_id}。\n程式即將關閉，請手動重新開啟。",
        )
        if self.on_artist_id_change_finished:
            self.on_artist_id_change_finished(old_artist_id, new_artist_id)

    def submit_artist_rating(self) -> None:
        artist = self.editing_artist
        if artist is None:
            self.set_status("找不到歌手。", error=True)
            return
        score = int(round(self.artist_rating_score_var.get()))
        affects_algorithm = self.artist_rating_type_var.get() == "影響演算法"
        try:
            self.rating_repository.add_artist_rating(
                artist.artist_id,
                score,
                affects_algorithm=affects_algorithm,
            )
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.artist_rating_status_label.configure(text=self._artist_rating_status_text(artist.artist_id))
        self.artist_rating_submit_button.configure(state="disabled")
        self.set_status(f"已送出歌手評分：{score}/10")

    def _artist_rating_status_text(self, artist_id: str) -> str:
        count = self.rating_repository.artist_rating_count(artist_id)
        score = self.rating_repository.artist_algorithm_score(artist_id)
        today = "今天已評過" if self.rating_repository.has_artist_rating_today(artist_id) else "今天尚未評分"
        return f"已記錄 {count} 筆評分\n演算法分數：{score:.2f} / 10\n{today}"

    def _update_artist_rating_label(self, value) -> None:
        score = int(round(float(value)))
        self.artist_rating_score_var.set(score)
        self.artist_rating_value_label.configure(text=f"{score} / 10")

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
