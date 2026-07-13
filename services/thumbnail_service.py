from io import BytesIO
from pathlib import Path

from PIL import Image
import requests

from config import CHANNEL_AVATAR_CACHE_DIR, CHANNEL_AVATAR_SIZE, THUMBNAIL_CACHE_DIR, THUMBNAIL_SIZE


class ThumbnailService:
    def get_thumbnail(self, video_id: str, url: str | None) -> Image.Image | None:
        return self._get_cached_image(THUMBNAIL_CACHE_DIR, video_id, url, THUMBNAIL_SIZE)

    def get_channel_avatar(self, channel_id: str, url: str | None) -> Image.Image | None:
        return self._get_cached_image(CHANNEL_AVATAR_CACHE_DIR, channel_id, url, CHANNEL_AVATAR_SIZE)

    def _get_cached_image(
        self, cache_dir: Path, cache_key: str, url: str | None, size: tuple[int, int]
    ) -> Image.Image | None:
        if not url:
            return None
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{cache_key}.jpg"
        try:
            if cache_path.exists():
                return self._open_and_resize(cache_path, size)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            image.thumbnail(size)
            image.save(cache_path, "JPEG", quality=85)
            return image
        except Exception:
            return None

    def _open_and_resize(self, path: Path, size: tuple[int, int]) -> Image.Image:
        image = Image.open(path).convert("RGB")
        image.thumbnail(size)
        return image
