import sqlite3

from database.connection import get_connection
from models.tag import TagCategory, TagOption


def _row_to_category(row: sqlite3.Row) -> TagCategory:
    return TagCategory(
        id=row["id"],
        name=row["name"],
        sort_order=row["sort_order"],
        is_available=bool(row["is_available"]),
    )


def _row_to_option(row: sqlite3.Row) -> TagOption:
    return TagOption(
        id=row["id"],
        category_id=row["category_id"],
        name=row["name"],
        sort_order=row["sort_order"],
        is_available=bool(row["is_available"]),
    )


class TagRepository:
    def list_categories(self, *, include_unavailable: bool = False) -> list[TagCategory]:
        where = "" if include_unavailable else "WHERE is_available = 1"
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, name, sort_order, is_available
                FROM tag_categories
                {where}
                ORDER BY sort_order, id
                """
            ).fetchall()
        return [_row_to_category(row) for row in rows]

    def list_options_by_category(
        self, category_id: int, *, include_unavailable: bool = False
    ) -> list[TagOption]:
        where = "category_id = ?"
        if not include_unavailable:
            where += " AND is_available = 1"
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, category_id, name, sort_order, is_available
                FROM tag_options
                WHERE {where}
                ORDER BY sort_order, id
                """,
                (category_id,),
            ).fetchall()
        return [_row_to_option(row) for row in rows]

    def list_options_grouped(self) -> dict[int, list[TagOption]]:
        grouped: dict[int, list[TagOption]] = {}
        for category in self.list_categories():
            grouped[category.id] = self.list_options_by_category(category.id)
        return grouped

    def list_unavailable_categories(self) -> list[TagCategory]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, name, sort_order, is_available
                FROM tag_categories
                WHERE is_available = 0
                ORDER BY sort_order, id
                """
            ).fetchall()
        return [_row_to_category(row) for row in rows]

    def list_unavailable_options(self) -> list[tuple[TagOption, str]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT tag_options.id, tag_options.category_id, tag_options.name,
                       tag_options.sort_order, tag_options.is_available,
                       tag_categories.name AS category_name
                FROM tag_options
                JOIN tag_categories ON tag_categories.id = tag_options.category_id
                WHERE tag_options.is_available = 0
                ORDER BY tag_categories.sort_order, tag_options.sort_order, tag_options.id
                """
            ).fetchall()
        return [(_row_to_option(row), row["category_name"]) for row in rows]

    def add_category(self, name: str) -> TagCategory:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("上層標籤名稱不能空白。")
        try:
            with get_connection() as connection:
                max_sort = connection.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM tag_categories"
                ).fetchone()[0]
                cursor = connection.execute(
                    """
                    INSERT INTO tag_categories (name, sort_order)
                    VALUES (?, ?)
                    """,
                    (cleaned, max_sort + 1),
                )
                row = connection.execute(
                    """
                    SELECT id, name, sort_order, is_available
                    FROM tag_categories
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("這個上層標籤已存在。") from exc
        return _row_to_category(row)

    def add_option(self, category_id: int, name: str) -> TagOption:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("下層標籤名稱不能空白。")
        try:
            with get_connection() as connection:
                category = connection.execute(
                    """
                    SELECT id FROM tag_categories
                    WHERE id = ? AND is_available = 1
                    """,
                    (category_id,),
                ).fetchone()
                if category is None:
                    raise ValueError("找不到可用的上層標籤。")
                max_sort = connection.execute(
                    """
                    SELECT COALESCE(MAX(sort_order), -1)
                    FROM tag_options
                    WHERE category_id = ?
                    """,
                    (category_id,),
                ).fetchone()[0]
                cursor = connection.execute(
                    """
                    INSERT INTO tag_options (category_id, name, sort_order)
                    VALUES (?, ?, ?)
                    """,
                    (category_id, cleaned, max_sort + 1),
                )
                row = connection.execute(
                    """
                    SELECT id, category_id, name, sort_order, is_available
                    FROM tag_options
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("這個下層標籤已存在。") from exc
        return _row_to_option(row)

    def set_category_available(self, category_id: int, is_available: bool) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE tag_categories SET is_available = ? WHERE id = ?",
                (1 if is_available else 0, category_id),
            )

    def set_option_available(self, option_id: int, is_available: bool) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE tag_options SET is_available = ? WHERE id = ?",
                (1 if is_available else 0, option_id),
            )

    def move_category(self, category_id: int, direction: int) -> bool:
        if direction not in (-1, 1):
            raise ValueError("排序方向不正確。")
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM tag_categories
                WHERE is_available = 1
                ORDER BY sort_order, id
                """
            ).fetchall()
            ids = [row["id"] for row in rows]
            if category_id not in ids:
                raise ValueError("找不到可排序的上層標籤。")
            index = ids.index(category_id)
            target_index = index + direction
            if target_index < 0 or target_index >= len(ids):
                return False
            ids[index], ids[target_index] = ids[target_index], ids[index]
            for sort_order, current_id in enumerate(ids):
                connection.execute(
                    "UPDATE tag_categories SET sort_order = ? WHERE id = ?",
                    (sort_order, current_id),
                )
        return True

    def move_option(self, option_id: int, direction: int) -> bool:
        if direction not in (-1, 1):
            raise ValueError("排序方向不正確。")
        with get_connection() as connection:
            option = connection.execute(
                """
                SELECT category_id
                FROM tag_options
                WHERE id = ? AND is_available = 1
                """,
                (option_id,),
            ).fetchone()
            if option is None:
                raise ValueError("找不到可排序的下層標籤。")
            rows = connection.execute(
                """
                SELECT id
                FROM tag_options
                WHERE category_id = ? AND is_available = 1
                ORDER BY sort_order, id
                """,
                (option["category_id"],),
            ).fetchall()
            ids = [row["id"] for row in rows]
            index = ids.index(option_id)
            target_index = index + direction
            if target_index < 0 or target_index >= len(ids):
                return False
            ids[index], ids[target_index] = ids[target_index], ids[index]
            for sort_order, current_id in enumerate(ids):
                connection.execute(
                    "UPDATE tag_options SET sort_order = ? WHERE id = ?",
                    (sort_order, current_id),
                )
        return True

    def category_usage_count(self, category_id: int) -> int:
        with get_connection() as connection:
            return connection.execute(
                """
                SELECT COUNT(*)
                FROM artist_tags
                WHERE category_id = ?
                """,
                (category_id,),
            ).fetchone()[0]

    def option_usage_count(self, option_id: int) -> int:
        with get_connection() as connection:
            return connection.execute(
                """
                SELECT COUNT(*)
                FROM artist_tags
                WHERE option_id = ?
                """,
                (option_id,),
            ).fetchone()[0]

    def delete_category_if_unused(self, category_id: int) -> None:
        usage_count = self.category_usage_count(category_id)
        if usage_count:
            raise ValueError(f"此上層標籤仍有 {usage_count} 筆歌手使用紀錄，不能刪除。")
        with get_connection() as connection:
            connection.execute("DELETE FROM tag_categories WHERE id = ?", (category_id,))

    def delete_option_if_unused(self, option_id: int) -> None:
        usage_count = self.option_usage_count(option_id)
        if usage_count:
            raise ValueError(f"此下層標籤仍有 {usage_count} 筆歌手使用紀錄，不能刪除。")
        with get_connection() as connection:
            connection.execute("DELETE FROM tag_options WHERE id = ?", (option_id,))

    def get_artist_option_ids(self, artist_id: str) -> set[int]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT option_id
                FROM artist_tags
                WHERE artist_id = ? COLLATE NOCASE
                """,
                (artist_id,),
            ).fetchall()
        return {row["option_id"] for row in rows}

    def replace_artist_tags(self, artist_id: str, option_ids: set[int]) -> None:
        with get_connection() as connection:
            connection.execute(
                "DELETE FROM artist_tags WHERE artist_id = ? COLLATE NOCASE",
                (artist_id,),
            )
            for option_id in option_ids:
                row = connection.execute(
                    """
                    SELECT category_id
                    FROM tag_options
                    WHERE id = ? AND is_available = 1
                    """,
                    (option_id,),
                ).fetchone()
                if row is None:
                    continue
                connection.execute(
                    """
                    INSERT INTO artist_tags (artist_id, category_id, option_id)
                    VALUES (?, ?, ?)
                    """,
                    (artist_id, row["category_id"], option_id),
                )
