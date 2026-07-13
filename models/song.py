from dataclasses import dataclass


@dataclass(frozen=True)
class Song:
    id: int | None
    artist_id: str
    youtube_video_id: str
    youtube_url: str
    original_title: str
    song_name: str
    file_name: str
    file_path: str
    thumbnail_url: str | None
    duration: int | None
    upload_date: str | None
    download_status: str
    downloaded_at: str | None = None

