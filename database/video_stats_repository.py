from datetime import datetime, timedelta

from database.connection import get_connection
from models.video import Video


SQLITE_BATCH_SIZE = 900


class VideoStatsRepository:
    def apply_cached_view_counts(self, videos: list[Video]) -> list[Video]:
        if not videos:
            return videos
        video_ids = [video.youtube_video_id for video in videos]
        cached: dict[str, int] = {}
        with get_connection() as connection:
            for batch in self._batches(video_ids):
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"""
                    SELECT youtube_video_id, view_count
                    FROM video_stats
                    WHERE youtube_video_id IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
                cached.update({row["youtube_video_id"]: row["view_count"] for row in rows})
        return [self._with_view_count(video, cached.get(video.youtube_video_id)) for video in videos]

    def stale_video_ids(self, videos: list[Video], *, max_age_days: int = 7) -> set[str]:
        if not videos:
            return set()
        video_ids = [video.youtube_video_id for video in videos]
        cutoff = datetime.now() - timedelta(days=max_age_days)
        checked_at_by_id: dict[str, str] = {}
        skipped_ids: set[str] = set()
        with get_connection() as connection:
            for batch in self._batches(video_ids):
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"""
                    SELECT youtube_video_id, view_count, updated_at, last_failed_at
                    FROM video_stats
                    WHERE youtube_video_id IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
                skipped_ids.update(
                    row["youtube_video_id"] for row in rows if row["view_count"] == -1
                )
                checked_at_by_id.update(
                    {
                        row["youtube_video_id"]: self._latest_timestamp(
                            row["updated_at"], row["last_failed_at"]
                        )
                        for row in rows
                    }
                )
        stale_ids: set[str] = set()
        for video_id in video_ids:
            if video_id in skipped_ids:
                continue
            checked_at = checked_at_by_id.get(video_id)
            if checked_at is None or self._parse_datetime(checked_at) < cutoff:
                stale_ids.add(video_id)
        return stale_ids

    def save_view_count(self, youtube_video_id: str, view_count: int | None) -> None:
        if view_count is None:
            return
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO video_stats (youtube_video_id, view_count, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(youtube_video_id) DO UPDATE SET
                    view_count = excluded.view_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (youtube_video_id, view_count),
            )

    def save_view_counts(self, videos: list[Video]) -> None:
        rows = [
            (video.youtube_video_id, video.view_count)
            for video in videos
            if video.view_count is not None
        ]
        if not rows:
            return
        with get_connection() as connection:
            connection.executemany(
                """
                INSERT INTO video_stats (youtube_video_id, view_count, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(youtube_video_id) DO UPDATE SET
                    view_count = excluded.view_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def mark_view_count_failed(self, youtube_video_id: str) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO video_stats (youtube_video_id, view_count, last_failed_at, updated_at)
                VALUES (?, 0, CURRENT_TIMESTAMP, '1970-01-01 00:00:00')
                ON CONFLICT(youtube_video_id) DO UPDATE SET
                    last_failed_at = CURRENT_TIMESTAMP
                """,
                (youtube_video_id,),
            )

    def mark_view_count_unavailable(self, youtube_video_id: str) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO video_stats (youtube_video_id, view_count, updated_at)
                VALUES (?, -1, CURRENT_TIMESTAMP)
                ON CONFLICT(youtube_video_id) DO UPDATE SET
                    view_count = -1,
                    updated_at = CURRENT_TIMESTAMP,
                    last_failed_at = NULL
                """,
                (youtube_video_id,),
            )

    def _with_view_count(self, video: Video, view_count: int | None) -> Video:
        if view_count is None:
            return video
        return Video(
            youtube_video_id=video.youtube_video_id,
            youtube_url=video.youtube_url,
            title=video.title,
            thumbnail_url=video.thumbnail_url,
            duration=video.duration,
            upload_date=video.upload_date,
            view_count=view_count,
            download_status=video.download_status,
            is_downloaded=video.is_downloaded,
            file_missing=video.file_missing,
        )

    def _parse_datetime(self, value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    def _latest_timestamp(self, first: str | None, second: str | None) -> str | None:
        if not first:
            return second
        if not second:
            return first
        return max(first, second, key=self._parse_datetime)

    def _batches(self, values: list[str]) -> list[list[str]]:
        return [
            values[index : index + SQLITE_BATCH_SIZE]
            for index in range(0, len(values), SQLITE_BATCH_SIZE)
        ]
