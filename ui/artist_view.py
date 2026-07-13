import re
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk

from database.artist_repository import ArtistRepository
from services.youtube_service import YouTubeService

ARTIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class ArtistView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        artist_repository: ArtistRepository,
        youtube_service: YouTubeService,
        on_artists_changed,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.artist_repository = artist_repository
        self.youtube_service = youtube_service
        self.on_artists_changed = on_artists_changed
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.channel_name_entries: dict[str, ctk.CTkEntry] = {}

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        form = ctk.CTkFrame(self)
        form.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="歌手 ID").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.artist_id_entry = ctk.CTkEntry(form, placeholder_text="例如 suisei")
        self.artist_id_entry.grid(row=0, column=1, sticky="ew", padx=12, pady=(12, 6))

        ctk.CTkLabel(form, text="YouTube 頻道網址").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.url_entry = ctk.CTkEntry(form, placeholder_text="https://www.youtube.com/@channel")
        self.url_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=6)

        self.add_button = ctk.CTkButton(form, text="新增歌手", command=self.add_artist)
        self.add_button.grid(row=2, column=1, sticky="e", padx=12, pady=(6, 12))

        self.status_label = ctk.CTkLabel(form, text="", anchor="w")
        self.status_label.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))

        ctk.CTkLabel(self, text="已新增歌手", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=1, column=0, sticky="nw", padx=8, pady=(8, 0)
        )
        self.artist_list = ctk.CTkScrollableFrame(self)
        self.artist_list.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
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
        self.set_status("正在取得頻道資料...")
        future = self.executor.submit(self._add_artist_worker, artist_id, url)
        future.add_done_callback(lambda done: self.after(0, self._handle_add_result, done))

    def _add_artist_worker(self, artist_id: str, url: str):
        channel = self.youtube_service.get_channel_info(url)
        return self.artist_repository.add_artist(
            artist_id=artist_id,
            youtube_url=channel.channel_url,
            channel_id=channel.channel_id,
            channel_name=channel.channel_name,
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
        self.set_status(f"已新增：{artist.artist_id} / {artist.channel_name}")
        self.reload_artists()
        self.on_artists_changed()

    def reload_artists(self) -> None:
        for child in self.artist_list.winfo_children():
            child.destroy()
        self.channel_name_entries.clear()
        artists = self.artist_repository.list_artists()
        if not artists:
            ctk.CTkLabel(self.artist_list, text="尚未新增歌手", anchor="w").grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            return
        for row, artist in enumerate(artists):
            frame = ctk.CTkFrame(self.artist_list)
            frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
            frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(frame, text=artist.artist_id, width=110, anchor="w").grid(
                row=0, column=0, sticky="w", padx=(10, 6), pady=10
            )
            entry = ctk.CTkEntry(frame)
            entry.insert(0, artist.channel_name)
            entry.grid(row=0, column=1, sticky="ew", padx=6, pady=10)
            self.channel_name_entries[artist.artist_id] = entry
            ctk.CTkButton(
                frame,
                text="更新名稱",
                width=90,
                command=lambda artist_id=artist.artist_id: self.update_channel_name(artist_id),
            ).grid(row=0, column=2, padx=(6, 10), pady=10)
            ctk.CTkLabel(frame, text=artist.channel_id, anchor="w").grid(
                row=1, column=1, columnspan=2, sticky="ew", padx=6, pady=(0, 10)
            )

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
        self.reload_artists()
        self.on_artists_changed()

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

    def destroy(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
