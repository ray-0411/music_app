import sqlite3

from database.connection import get_connection
from models.artist import Artist


def _row_to_artist(row: sqlite3.Row) -> Artist:
    return Artist(
        id=row["id"],
        artist_id=row["artist_id"],
        youtube_url=row["youtube_url"],
        channel_id=row["channel_id"],
        channel_name=row["channel_name"],
        created_at=row["created_at"],
    )


class ArtistRepository:
    def list_artists(self) -> list[Artist]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, artist_id, youtube_url, channel_id, channel_name, created_at
                FROM artists
                ORDER BY artist_id COLLATE NOCASE
                """
            ).fetchall()
        return [_row_to_artist(row) for row in rows]

    def add_artist(
        self, artist_id: str, youtube_url: str, channel_id: str, channel_name: str
    ) -> Artist:
        try:
            with get_connection() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO artists (artist_id, youtube_url, channel_id, channel_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    (artist_id, youtube_url, channel_id, channel_name),
                )
                row = connection.execute(
                    """
                    SELECT id, artist_id, youtube_url, channel_id, channel_name, created_at
                    FROM artists
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "artists.artist_id" in message:
                raise ValueError("歌手 ID 已存在。") from exc
            if "artists.channel_id" in message:
                raise ValueError("這個 YouTube 頻道已存在。") from exc
            raise ValueError("歌手資料重複或不合法。") from exc
        return _row_to_artist(row)

    def get_by_artist_id(self, artist_id: str) -> Artist | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, artist_id, youtube_url, channel_id, channel_name, created_at
                FROM artists
                WHERE artist_id = ? COLLATE NOCASE
                """,
                (artist_id,),
            ).fetchone()
        return _row_to_artist(row) if row else None

    def update_channel_name(self, artist_id: str, channel_name: str) -> Artist:
        if not channel_name.strip():
            raise ValueError("頻道名稱不能空白。")
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE artists
                SET channel_name = ?
                WHERE artist_id = ? COLLATE NOCASE
                """,
                (channel_name.strip(), artist_id),
            )
            row = connection.execute(
                """
                SELECT id, artist_id, youtube_url, channel_id, channel_name, created_at
                FROM artists
                WHERE artist_id = ? COLLATE NOCASE
                """,
                (artist_id,),
            ).fetchone()
        if row is None:
            raise ValueError("找不到歌手。")
        return _row_to_artist(row)
