from dataclasses import dataclass


@dataclass(frozen=True)
class Artist:
    id: int | None
    artist_id: str
    youtube_url: str
    channel_id: str
    channel_name: str
    created_at: str | None = None

