from database.connection import get_connection


class RatingRepository:
    LATEST_WEIGHTS = [5, 3, 2, 1, 1]
    ALL_AVERAGE_WEIGHT = 3
    DEFAULT_SCORE = 5.0

    def add_song_rating(
        self,
        song_id: int,
        score: int,
        *,
        affects_algorithm: bool,
        enforce_daily_limit: bool = True,
    ) -> None:
        cleaned_score = self._validate_score(score)
        with get_connection() as connection:
            if enforce_daily_limit and self._has_song_rating_today(connection, song_id):
                raise ValueError("這首歌今天已經評分過，請明天再評。")
            connection.execute(
                """
                INSERT INTO song_ratings (song_id, score, affects_algorithm)
                VALUES (?, ?, ?)
                """,
                (song_id, cleaned_score, 1 if affects_algorithm else 0),
            )

    def add_artist_rating(
        self,
        artist_id: str,
        score: int,
        *,
        affects_algorithm: bool,
        enforce_daily_limit: bool = True,
    ) -> None:
        cleaned_score = self._validate_score(score)
        with get_connection() as connection:
            if enforce_daily_limit and self._has_artist_rating_today(connection, artist_id):
                raise ValueError("這位歌手今天已經評分過，請明天再評。")
            connection.execute(
                """
                INSERT INTO artist_ratings (artist_id, score, affects_algorithm)
                VALUES (?, ?, ?)
                """,
                (artist_id, cleaned_score, 1 if affects_algorithm else 0),
            )

    def song_rating_count(self, song_id: int) -> int:
        with get_connection() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM song_ratings WHERE song_id = ?",
                (song_id,),
            ).fetchone()[0]

    def has_song_rating_today(self, song_id: int) -> bool:
        with get_connection() as connection:
            return self._has_song_rating_today(connection, song_id)

    def song_algorithm_score(self, song_id: int) -> float:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT score
                FROM song_ratings
                WHERE song_id = ? AND affects_algorithm = 1
                ORDER BY created_at DESC, id DESC
                """,
                (song_id,),
            ).fetchall()
        return self._calculate_algorithm_score([row["score"] for row in rows])

    def artist_rating_count(self, artist_id: str) -> int:
        with get_connection() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM artist_ratings WHERE artist_id = ? COLLATE NOCASE",
                (artist_id,),
            ).fetchone()[0]

    def has_artist_rating_today(self, artist_id: str) -> bool:
        with get_connection() as connection:
            return self._has_artist_rating_today(connection, artist_id)

    def artist_algorithm_score(self, artist_id: str) -> float:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT score
                FROM artist_ratings
                WHERE artist_id = ? COLLATE NOCASE AND affects_algorithm = 1
                ORDER BY created_at DESC, id DESC
                """,
                (artist_id,),
            ).fetchall()
        return self._calculate_algorithm_score([row["score"] for row in rows])

    def _calculate_algorithm_score(self, scores: list[int]) -> float:
        if not scores:
            return self.DEFAULT_SCORE
        all_average = sum(scores) / len(scores)
        latest_scores = scores[: len(self.LATEST_WEIGHTS)]
        weighted_total = 0.0
        for index, weight in enumerate(self.LATEST_WEIGHTS):
            score = latest_scores[index] if index < len(latest_scores) else all_average
            weighted_total += score * weight
        weighted_total += all_average * self.ALL_AVERAGE_WEIGHT
        return weighted_total / (sum(self.LATEST_WEIGHTS) + self.ALL_AVERAGE_WEIGHT)

    def _has_song_rating_today(self, connection, song_id: int) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM song_ratings
            WHERE song_id = ?
              AND date(created_at, 'localtime') = date('now', 'localtime')
            LIMIT 1
            """,
            (song_id,),
        ).fetchone()
        return row is not None

    def _has_artist_rating_today(self, connection, artist_id: str) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM artist_ratings
            WHERE artist_id = ? COLLATE NOCASE
              AND date(created_at, 'localtime') = date('now', 'localtime')
            LIMIT 1
            """,
            (artist_id,),
        ).fetchone()
        return row is not None

    def _validate_score(self, score: int) -> int:
        try:
            cleaned_score = int(score)
        except (TypeError, ValueError) as exc:
            raise ValueError("評分必須是 0 到 10 的整數。") from exc
        if cleaned_score < 0 or cleaned_score > 10:
            raise ValueError("評分必須是 0 到 10。")
        return cleaned_score
