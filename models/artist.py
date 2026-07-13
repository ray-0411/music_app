from dataclasses import dataclass


@dataclass(frozen=True)
class Artist:
    id: int | None
    artist_id: str
    youtube_url: str
    channel_id: str
    channel_name: str
    avatar_url: str | None = None
    created_at: str | None = None
