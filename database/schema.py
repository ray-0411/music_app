from database.connection import get_connection


SCHEMA_VERSION = 1


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_id TEXT NOT NULL COLLATE NOCASE UNIQUE,
                youtube_url TEXT NOT NULL,
                channel_id TEXT NOT NULL UNIQUE,
                channel_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_id TEXT NOT NULL COLLATE NOCASE,
                youtube_video_id TEXT NOT NULL UNIQUE,
                youtube_url TEXT NOT NULL,
                original_title TEXT NOT NULL,
                song_name TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                thumbnail_url TEXT,
                duration INTEGER,
                upload_date TEXT,
                download_status TEXT NOT NULL,
                downloaded_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_songs_artist_id ON songs(artist_id)"
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO schema_meta (key, value)
            VALUES ('schema_version', ?)
            """,
            (str(SCHEMA_VERSION),),
        )

