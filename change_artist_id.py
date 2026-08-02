import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from config import DOWNLOADS_DIR
from database.connection import get_connection
from database.schema import initialize_database
from utils.filename import build_mp3_filename


ARTIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class SongMove:
    song_id: int
    old_path: Path
    new_path: Path
    new_file_name: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Change an artist_id safely.")
    parser.add_argument("old_artist_id", nargs="?", help="Current artist_id")
    parser.add_argument("new_artist_id", nargs="?", help="New artist_id")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    old_artist_id = args.old_artist_id or input("目前 artist_id: ").strip()
    new_artist_id = args.new_artist_id or input("新的 artist_id: ").strip()

    initialize_database()
    try:
        plan = build_change_plan(old_artist_id, new_artist_id)
    except ValueError as exc:
        print(exc)
        return
    print_plan(plan, old_artist_id, new_artist_id)

    if not args.yes:
        answer = input("確認修改？輸入 YES 繼續: ").strip()
        if answer != "YES":
            print("已取消。")
            return

    apply_change(old_artist_id, new_artist_id, plan)
    print("完成。")


def build_change_plan(old_artist_id: str, new_artist_id: str) -> list[SongMove]:
    validate_artist_ids(old_artist_id, new_artist_id)
    old_dir = DOWNLOADS_DIR / old_artist_id
    new_dir = DOWNLOADS_DIR / new_artist_id
    with get_connection() as connection:
        old_artist = connection.execute(
            "SELECT artist_id FROM artists WHERE artist_id = ? COLLATE NOCASE",
            (old_artist_id,),
        ).fetchone()
        if old_artist is None:
            raise ValueError(f"找不到 artist_id：{old_artist_id}")
        duplicate = connection.execute(
            "SELECT artist_id FROM artists WHERE artist_id = ? COLLATE NOCASE",
            (new_artist_id,),
        ).fetchone()
        if duplicate is not None:
            raise ValueError(f"新的 artist_id 已存在：{new_artist_id}")
        song_rows = connection.execute(
            """
            SELECT id, song_name, file_name, file_path
            FROM songs
            WHERE artist_id = ? COLLATE NOCASE
            ORDER BY id
            """,
            (old_artist_id,),
        ).fetchall()

    if new_dir.exists() and any(new_dir.iterdir()):
        raise ValueError(f"目標資料夾已存在且不是空的：{new_dir}")

    moves: list[SongMove] = []
    planned_paths: set[Path] = set()
    for row in song_rows:
        old_path = Path(row["file_path"])
        new_file_name = build_mp3_filename(new_artist_id, row["song_name"])
        new_path = new_dir / new_file_name
        normalized_new_path = new_path.resolve()
        if normalized_new_path in planned_paths:
            raise ValueError(f"新檔名重複：{new_file_name}")
        planned_paths.add(normalized_new_path)
        if new_path.exists() and old_path.resolve() != normalized_new_path:
            raise ValueError(f"目標檔案已存在：{new_path}")
        moves.append(
            SongMove(
                song_id=row["id"],
                old_path=old_path,
                new_path=new_path,
                new_file_name=new_file_name,
            )
        )
    return moves


def validate_artist_ids(old_artist_id: str, new_artist_id: str) -> None:
    if not old_artist_id or not new_artist_id:
        raise ValueError("artist_id 不能空白。")
    if not ARTIST_ID_PATTERN.fullmatch(new_artist_id):
        raise ValueError("新的 artist_id 只能使用英文、數字、底線與減號。")
    if old_artist_id.lower() == new_artist_id.lower():
        raise ValueError("新的 artist_id 必須和原本不同。")


def print_plan(moves: list[SongMove], old_artist_id: str, new_artist_id: str) -> None:
    print(f"{old_artist_id} -> {new_artist_id}")
    print(f"歌曲數量：{len(moves)}")
    print(f"資料夾：{DOWNLOADS_DIR / old_artist_id} -> {DOWNLOADS_DIR / new_artist_id}")
    if moves:
        print("前 5 筆檔名預覽：")
        for move in moves[:5]:
            print(f"- {move.old_path.name} -> {move.new_path.name}")


def apply_change(old_artist_id: str, new_artist_id: str, moves: list[SongMove]) -> None:
    old_dir = DOWNLOADS_DIR / old_artist_id
    new_dir = DOWNLOADS_DIR / new_artist_id
    moved: list[tuple[Path, Path]] = []
    try:
        new_dir.mkdir(parents=True, exist_ok=True)
        for move in moves:
            if move.old_path.exists():
                move.new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(move.old_path), str(move.new_path))
                moved.append((move.new_path, move.old_path))

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE artists
                SET artist_id = ?
                WHERE artist_id = ? COLLATE NOCASE
                """,
                (new_artist_id, old_artist_id),
            )
            for move in moves:
                connection.execute(
                    """
                    UPDATE songs
                    SET file_name = ?, file_path = ?
                    WHERE id = ?
                    """,
                    (move.new_file_name, str(move.new_path), move.song_id),
                )

        remove_empty_directory(old_dir)
    except Exception:
        for current_path, original_path in reversed(moved):
            if current_path.exists() and not original_path.exists():
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(current_path), str(original_path))
        remove_empty_directory(new_dir)
        raise


def remove_empty_directory(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


if __name__ == "__main__":
    main()
