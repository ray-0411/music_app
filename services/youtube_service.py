from dataclasses import dataclass

import yt_dlp

from config import VIDEO_BATCH_SIZE
from models.video import Video


@dataclass(frozen=True)
class ChannelInfo:
    input_url: str
    channel_id: str
    channel_name: str
    channel_url: str


@dataclass(frozen=True)
class VideoListResult:
    videos: list[Video]
    limited: bool
    total_count: int | None


class YouTubeService:
    def get_channel_info(self, url: str) -> ChannelInfo:
        options = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "playlistend": 1,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise RuntimeError(f"無法取得頻道資料：{exc}") from exc

        channel_id = info.get("channel_id") or info.get("id") or info.get("uploader_id")
        channel_name = info.get("channel") or info.get("uploader") or info.get("title")
        channel_url = info.get("channel_url") or info.get("webpage_url") or url
        if not channel_id or not channel_name:
            raise RuntimeError("無法從此網址取得 YouTube channel ID 或頻道名稱。")
        return ChannelInfo(url, channel_id, channel_name, channel_url)

    def list_channel_videos(
        self, channel_url: str, start: int = 0, limit: int = VIDEO_BATCH_SIZE
    ) -> VideoListResult:
        videos_url = self._videos_url(channel_url)
        options = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "playliststart": start + 1,
            "playlistend": start + limit,
            "ignoreerrors": True,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(videos_url, download=False)
        except Exception as exc:
            raise RuntimeError(f"無法取得影片列表：{exc}") from exc

        entries = [entry for entry in info.get("entries", []) if entry]
        total_count = info.get("playlist_count")
        limited = total_count is not None and total_count > start + len(entries)
        if total_count is None and len(entries) == limit:
            limited = True
        videos = [self._entry_to_video(entry) for entry in entries[:limit]]
        return VideoListResult(videos=videos, limited=limited, total_count=total_count)

    def _entry_to_video(self, entry: dict) -> Video:
        video_id = entry.get("id")
        url = entry.get("url") or entry.get("webpage_url")
        if url and url.startswith("http"):
            youtube_url = url
        else:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        thumbnail_url = entry.get("thumbnail")
        thumbnails = entry.get("thumbnails") or []
        if not thumbnail_url and thumbnails:
            thumbnail_url = thumbnails[-1].get("url")
        return Video(
            youtube_video_id=video_id,
            youtube_url=youtube_url,
            title=entry.get("title") or "(未命名影片)",
            thumbnail_url=thumbnail_url,
            duration=entry.get("duration"),
            upload_date=entry.get("upload_date"),
        )

    def _videos_url(self, channel_url: str) -> str:
        clean = channel_url.rstrip("/")
        if clean.endswith("/videos"):
            return clean
        return f"{clean}/videos"
