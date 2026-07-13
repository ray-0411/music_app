from pathlib import Path

import customtkinter as ctk

from database.song_repository import SongRepository
from models.song import Song
from services.song_service import SongService


class SongManagementView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        song_repository: SongRepository,
        song_service: SongService,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.song_repository = song_repository
        self.song_service = song_service
        self.song_entries: dict[int, ctk.CTkEntry] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.refresh_button = ctk.CTkButton(toolbar, text="重新整理", command=self.reload_songs)
        self.refresh_button.pack(side="left", padx=12, pady=10)
        self.status_label = ctk.CTkLabel(toolbar, text="", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        self.song_list = ctk.CTkScrollableFrame(self)
        self.song_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.song_list.grid_columnconfigure(0, weight=1)
        self.reload_songs()

    def reload_songs(self) -> None:
        for child in self.song_list.winfo_children():
            child.destroy()
        self.song_entries.clear()
        songs = self.song_repository.list_songs()
        if not songs:
            ctk.CTkLabel(self.song_list, text="尚無已下載歌曲", anchor="w").grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            self.set_status("")
            return
        for row, song in enumerate(songs):
            self._render_song(row, song)
        self.set_status(f"共 {len(songs)} 首下載紀錄。")

    def _render_song(self, row: int, song: Song) -> None:
        frame = ctk.CTkFrame(self.song_list)
        frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        frame.grid_columnconfigure(1, weight=1)

        status = self._song_status(song)
        ctk.CTkLabel(frame, text=song.artist_id, width=90, anchor="w").grid(
            row=0, column=0, sticky="nw", padx=(10, 6), pady=10
        )

        entry = ctk.CTkEntry(frame)
        entry.insert(0, song.song_name)
        entry.grid(row=0, column=1, sticky="ew", padx=6, pady=(10, 4))
        if song.id is not None:
            self.song_entries[song.id] = entry

        apply_button = ctk.CTkButton(
            frame,
            text="改名",
            width=72,
            command=lambda song_id=song.id: self.rename_song(song_id),
        )
        apply_button.grid(row=0, column=2, padx=(6, 10), pady=10)

        detail = (
            f"原始標題：{song.original_title}\n"
            f"檔案：{song.file_path}\n"
            f"狀態：{status}"
        )
        ctk.CTkLabel(frame, text=detail, anchor="w", justify="left", wraplength=760).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=6, pady=(0, 10)
        )

    def rename_song(self, song_id: int | None) -> None:
        if song_id is None:
            self.set_status("找不到歌曲 ID。", error=True)
            return
        entry = self.song_entries.get(song_id)
        if entry is None:
            self.set_status("找不到歌曲輸入框。", error=True)
            return
        try:
            song = self.song_service.rename_song(song_id, entry.get())
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.set_status(f"已改名：{song.file_name}")
        self.reload_songs()

    def _song_status(self, song: Song) -> str:
        if song.download_status == "downloaded" and not Path(song.file_path).exists():
            return "檔案遺失"
        return song.download_status

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)

