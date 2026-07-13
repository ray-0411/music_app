from io import BytesIO
from pathlib import Path

from PIL import Image
import requests

from config import THUMBNAIL_CACHE_DIR, THUMBNAIL_SIZE


class ThumbnailService:
    def get_thumbnail(self, video_id: str, url: str | None) -> Image.Image | None:
        if not url:
            return None
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = THUMBNAIL_CACHE_DIR / f"{video_id}.jpg"
        try:
            if cache_path.exists():
                return self._open_and_resize(cache_path)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            image.thumbnail(THUMBNAIL_SIZE)
            image.save(cache_path, "JPEG", quality=85)
            return image
        except Exception:
            return None

    def _open_and_resize(self, path: Path) -> Image.Image:
        image = Image.open(path).convert("RGB")
        image.thumbnail(THUMBNAIL_SIZE)
        return image

