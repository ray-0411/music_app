from database.connection import get_connection


SCHEMA_VERSION = 3


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
                avatar_url TEXT,
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
            CREATE TABLE IF NOT EXISTS tag_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_available INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tag_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_available INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES tag_categories(id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                UNIQUE(category_id, name)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artist_tags (
                artist_id TEXT NOT NULL COLLATE NOCASE,
                category_id INTEGER NOT NULL,
                option_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (artist_id, option_id),
                FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES tag_categories(id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (option_id) REFERENCES tag_options(id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_artist_tags_artist_id ON artist_tags(artist_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tag_options_category_id ON tag_options(category_id)"
        )
        _ensure_column(connection, "artists", "avatar_url", "TEXT")
        _ensure_column(connection, "songs", "duration", "INTEGER")
        _ensure_column(connection, "songs", "upload_date", "TEXT")
        _seed_default_tag_categories(connection)
        connection.execute(
            """
            INSERT OR REPLACE INTO schema_meta (key, value)
            VALUES ('schema_version', ?)
            """,
            (str(SCHEMA_VERSION),),
        )


def _ensure_column(connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _seed_default_tag_categories(connection) -> None:
    defaults = ["性別", "團體", "類型", "其他"]
    for index, name in enumerate(defaults):
        connection.execute(
            """
            INSERT OR IGNORE INTO tag_categories (name, sort_order)
            VALUES (?, ?)
            """,
            (name, index),
        )
