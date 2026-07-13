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


def strip_artist_prefix(artist_id: str, value: str) -> str:
    prefix = f"{artist_id}_"
    cleaned = value.strip()
    while cleaned.lower().startswith(prefix.lower()):
        cleaned = cleaned[len(prefix):].strip()
    return cleaned


def build_song_name(artist_id: str, title: str) -> str:
    return sanitize_filename_stem(strip_artist_prefix(artist_id, title))


def build_mp3_filename(artist_id: str, title: str) -> str:
    song_name = build_song_name(artist_id, title)
    file_stem = sanitize_filename_stem(f"{artist_id}_{song_name}")
    return f"{file_stem}.mp3"
