from pathlib import Path

from database.connection import get_connection
from models.song import Song
from models.video import Video


def _row_to_song(row) -> Song:
    return Song(
        id=row["id"],
        artist_id=row["artist_id"],
        youtube_video_id=row["youtube_video_id"],
        youtube_url=row["youtube_url"],
        original_title=row["original_title"],
        song_name=row["song_name"],
        file_name=row["file_name"],
        file_path=row["file_path"],
        thumbnail_url=row["thumbnail_url"],
        duration=row["duration"],
        upload_date=row["upload_date"],
        download_status=row["download_status"],
        downloaded_at=row["downloaded_at"],
    )


class SongRepository:
    def list_songs(self) -> list[Song]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, artist_id, youtube_video_id, youtube_url, original_title,
                       song_name, file_name, file_path, thumbnail_url, duration,
                       upload_date, download_status, downloaded_at
                FROM songs
                ORDER BY downloaded_at DESC, id DESC
                """
            ).fetchall()
        return [_row_to_song(row) for row in rows]

    def get_by_id(self, song_id: int) -> Song | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, artist_id, youtube_video_id, youtube_url, original_title,
                       song_name, file_name, file_path, thumbnail_url, duration,
                       upload_date, download_status, downloaded_at
                FROM songs
                WHERE id = ?
                """,
                (song_id,),
            ).fetchone()
        return _row_to_song(row) if row else None

    def get_by_video_id(self, youtube_video_id: str) -> Song | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, artist_id, youtube_video_id, youtube_url, original_title,
                       song_name, file_name, file_path, thumbnail_url, duration,
                       upload_date, download_status, downloaded_at
                FROM songs
                WHERE youtube_video_id = ?
                """,
                (youtube_video_id,),
            ).fetchone()
        return _row_to_song(row) if row else None

    def downloaded_video_ids_for_artist(self, artist_id: str) -> dict[str, Song]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, artist_id, youtube_video_id, youtube_url, original_title,
                       song_name, file_name, file_path, thumbnail_url, duration,
                       upload_date, download_status, downloaded_at
                FROM songs
                WHERE artist_id = ? COLLATE NOCASE
                """,
                (artist_id,),
            ).fetchall()
        return {row["youtube_video_id"]: _row_to_song(row) for row in rows}

    def save_downloaded_song(
        self,
        *,
        artist_id: str,
        video: Video,
        song_name: str,
        file_name: str,
        file_path: Path,
    ) -> Song:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO songs (
                    artist_id, youtube_video_id, youtube_url, original_title,
                    song_name, file_name, file_path, thumbnail_url, duration,
                    upload_date, download_status, downloaded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'downloaded', CURRENT_TIMESTAMP)
                ON CONFLICT(youtube_video_id) DO UPDATE SET
                    download_status = excluded.download_status,
                    file_name = excluded.file_name,
                    file_path = excluded.file_path,
                    song_name = excluded.song_name,
                    downloaded_at = CURRENT_TIMESTAMP
                """,
                (
                    artist_id,
                    video.youtube_video_id,
                    video.youtube_url,
                    video.title,
                    song_name,
                    file_name,
                    str(file_path),
                    video.thumbnail_url,
                    video.duration,
                    video.upload_date,
                ),
            )
            row = connection.execute(
                """
                SELECT id, artist_id, youtube_video_id, youtube_url, original_title,
                       song_name, file_name, file_path, thumbnail_url, duration,
                       upload_date, download_status, downloaded_at
                FROM songs
                WHERE youtube_video_id = ?
                """,
                (video.youtube_video_id,),
            ).fetchone()
        return _row_to_song(row)

    def mark_video_states(self, artist_id: str, videos: list[Video]) -> list[Video]:
        songs = self.downloaded_video_ids_for_artist(artist_id)
        marked: list[Video] = []
        for video in videos:
            song = songs.get(video.youtube_video_id)
            if song is None:
                marked.append(video)
                continue
            file_missing = song.download_status == "downloaded" and not Path(song.file_path).exists()
            status = "file_missing" if file_missing else song.download_status
            marked.append(
                Video(
                    youtube_video_id=video.youtube_video_id,
                    youtube_url=video.youtube_url,
                    title=video.title,
                    thumbnail_url=video.thumbnail_url,
                    duration=video.duration,
                    upload_date=video.upload_date,
                    download_status=status,
                    is_downloaded=song.download_status == "downloaded" and not file_missing,
                    file_missing=file_missing,
                )
            )
        return marked

    def update_song_file_info(
        self, song_id: int, *, song_name: str, file_name: str, file_path: Path
    ) -> Song:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE songs
                SET song_name = ?, file_name = ?, file_path = ?
                WHERE id = ?
                """,
                (song_name, file_name, str(file_path), song_id),
            )
            row = connection.execute(
                """
                SELECT id, artist_id, youtube_video_id, youtube_url, original_title,
                       song_name, file_name, file_path, thumbnail_url, duration,
                       upload_date, download_status, downloaded_at
                FROM songs
                WHERE id = ?
                """,
                (song_id,),
            ).fetchone()
        if row is None:
            raise ValueError("找不到歌曲。")
        return _row_to_song(row)
