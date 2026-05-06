import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.config import get_settings


def _connect() -> sqlite3.Connection:
    path = get_settings().sqlite_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_knowledge_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                vector_count INTEGER NOT NULL,
                upload_time TEXT NOT NULL,
                file_path TEXT NOT NULL,
                md5 TEXT NOT NULL
            )
            """
        )


def add_file(filename: str, file_type: str, file_path: str, md5: str, chunk_count: int) -> dict:
    item = {
        "id": str(uuid4()),
        "filename": filename,
        "file_type": file_type,
        "chunk_count": chunk_count,
        "vector_count": chunk_count,
        "upload_time": datetime.now().isoformat(timespec="seconds"),
        "file_path": file_path,
        "md5": md5,
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO knowledge_files
            VALUES (:id, :filename, :file_type, :chunk_count, :vector_count, :upload_time, :file_path, :md5)
            """,
            item,
        )
    return item


def list_files() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM knowledge_files ORDER BY upload_time DESC").fetchall()
    return [dict(row) for row in rows]


def get_file(file_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM knowledge_files WHERE id = ?", (file_id,)).fetchone()
    return dict(row) if row else None


def delete_file(file_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM knowledge_files WHERE id = ?", (file_id,))

