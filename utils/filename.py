import re

WINDOWS_FORBIDDEN_CHARS = r'<>:"/\|?*'
MAX_FILENAME_STEM_LENGTH = 150


def sanitize_filename_stem(value: str, max_length: int = MAX_FILENAME_STEM_LENGTH) -> str:
    cleaned = "".join("_" if char in WINDOWS_FORBIDDEN_CHARS else char for char in value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(".")
    if not cleaned:
        cleaned = "untitled"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned or "untitled"


def build_song_name(artist_id: str, title: str) -> str:
    return sanitize_filename_stem(f"{artist_id}_{title}")


def build_mp3_filename(artist_id: str, title: str) -> str:
    return f"{build_song_name(artist_id, title)}.mp3"

