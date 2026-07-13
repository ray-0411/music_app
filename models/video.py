from dataclasses import dataclass


@dataclass(frozen=True)
class Video:
    youtube_video_id: str
    youtube_url: str
    title: str
    thumbnail_url: str | None
    duration: int | None
    upload_date: str | None
    download_status: str = "not_downloaded"
    is_downloaded: bool = False
    file_missing: bool = False

