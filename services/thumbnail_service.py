from io import BytesIO
from pathlib import Path

from PIL import Image
import requests

from config import (
    ARTIST_IMAGE_DIR,
    CACHE_DIR,
    CHANNEL_AVATAR_SIZE,
    PLAYER_COVER_SIZE,
    SONG_IMAGE_DIR,
    THUMBNAIL_CACHE_DIR,
    THUMBNAIL_SIZE,
)


LEGACY_CHANNEL_AVATAR_DIR = CACHE_DIR / "channel_avatars"


class ThumbnailService:
    def get_thumbnail(self, video_id: str, url: str | None) -> Image.Image | None:
        return self._get_cached_image(
            THUMBNAIL_CACHE_DIR,
            f"{video_id}_preview",
            self._prefer_preview_youtube_thumbnail(url),
            THUMBNAIL_SIZE,
            fallback_url=url,
        )

    def get_channel_avatar(self, channel_id: str, url: str | None) -> Image.Image | None:
        return self._get_cached_image(
            ARTIST_IMAGE_DIR,
            channel_id,
            url,
            CHANNEL_AVATAR_SIZE,
            fallback_dirs=[LEGACY_CHANNEL_AVATAR_DIR],
        )

    def get_existing_channel_avatar(self, channel_id: str) -> Image.Image | None:
        return self._get_existing_cached_image(
            ARTIST_IMAGE_DIR,
            channel_id,
            CHANNEL_AVATAR_SIZE,
            fallback_dirs=[LEGACY_CHANNEL_AVATAR_DIR],
        )

    def get_song_thumbnail(self, video_id: str, url: str | None) -> Image.Image | None:
        return self._get_cached_image(
            SONG_IMAGE_DIR,
            video_id,
            self._prefer_song_cover_youtube_thumbnail(url),
            PLAYER_COVER_SIZE,
            fallback_url=url,
        )

    def get_existing_song_thumbnail(self, video_id: str) -> Image.Image | None:
        return self._get_existing_cached_image(
            SONG_IMAGE_DIR,
            video_id,
            THUMBNAIL_SIZE,
            fallback_dirs=[THUMBNAIL_CACHE_DIR],
        )

    def get_existing_song_cover(self, video_id: str) -> Image.Image | None:
        return self._get_existing_cached_image(
            SONG_IMAGE_DIR,
            video_id,
            PLAYER_COVER_SIZE,
            fallback_dirs=[THUMBNAIL_CACHE_DIR],
        )

    def _get_cached_image(
        self,
        cache_dir: Path,
        cache_key: str,
        url: str | None,
        size: tuple[int, int],
        fallback_dirs: list[Path] | None = None,
        fallback_url: str | None = None,
    ) -> Image.Image | None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{cache_key}.jpg"
        try:
            if cache_path.exists():
                return self._open_and_resize(cache_path, size)
            for fallback_dir in fallback_dirs or []:
                fallback_path = fallback_dir / f"{cache_key}.jpg"
                if fallback_path.exists():
                    image = self._open_and_resize(fallback_path, size)
                    image.save(cache_path, "JPEG", quality=85)
                    return image
            if not url:
                return None
            response = self._download_image(url, fallback_url)
            if cache_dir == SONG_IMAGE_DIR:
                cache_path.write_bytes(response.content)
            image = Image.open(BytesIO(response.content)).convert("RGB")
            image.thumbnail(size)
            if cache_dir != SONG_IMAGE_DIR:
                image.save(cache_path, "JPEG", quality=95)
            return image
        except Exception:
            return None

    def _download_image(self, url: str, fallback_url: str | None = None):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response
        except Exception:
            if not fallback_url or fallback_url == url:
                raise
            response = requests.get(fallback_url, timeout=10)
            response.raise_for_status()
            return response

    def _get_existing_cached_image(
        self,
        cache_dir: Path,
        cache_key: str,
        size: tuple[int, int],
        fallback_dirs: list[Path] | None = None,
    ) -> Image.Image | None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{cache_key}.jpg"
        try:
            if cache_path.exists():
                return self._open_and_resize(cache_path, size)
            for fallback_dir in fallback_dirs or []:
                fallback_path = fallback_dir / f"{cache_key}.jpg"
                if fallback_path.exists():
                    image = self._open_and_resize(fallback_path, size)
                    image.save(cache_path, "JPEG", quality=95)
                    return image
        except Exception:
            return None
        return None

    def _open_and_resize(self, path: Path, size: tuple[int, int]) -> Image.Image:
        image = Image.open(path).convert("RGB")
        image.thumbnail(size)
        return image

    def _prefer_song_cover_youtube_thumbnail(self, url: str | None) -> str | None:
        if not url or "ytimg.com" not in url:
            return url
        base_url = url.split("?", 1)[0]
        replacements = [
            "hqdefault.jpg",
            "mqdefault.jpg",
            "sddefault.jpg",
            "default.jpg",
            "hqdefault.webp",
            "mqdefault.webp",
            "sddefault.webp",
            "default.webp",
        ]
        for name in replacements:
            if base_url.endswith(name):
                return base_url[: -len(name)] + "maxresdefault.jpg"
        return base_url

    def _prefer_preview_youtube_thumbnail(self, url: str | None) -> str | None:
        if not url or "ytimg.com" not in url:
            return url
        base_url = url.split("?", 1)[0]
        replacements = [
            "hqdefault.jpg",
            "mqdefault.jpg",
            "sddefault.jpg",
            "maxresdefault.jpg",
            "hqdefault.webp",
            "mqdefault.webp",
            "sddefault.webp",
            "maxresdefault.webp",
        ]
        for name in replacements:
            if base_url.endswith(name):
                return base_url[: -len(name)] + "default.jpg"
        return base_url
