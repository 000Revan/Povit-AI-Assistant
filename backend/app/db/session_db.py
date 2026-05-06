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


def init_session_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )


def create_session(title: str = "新会话") -> dict:
    item = {"id": str(uuid4()), "title": title, "created_at": datetime.now().isoformat(timespec="seconds")}
    with _connect() as conn:
        conn.execute("INSERT INTO sessions VALUES (:id, :title, :created_at)", item)
    return item


def list_sessions() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def add_message(session_id: str, role: str, content: str) -> dict:
    item = {
        "id": str(uuid4()),
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with _connect() as conn:
        conn.execute("INSERT INTO messages VALUES (:id, :session_id, :role, :content, :created_at)", item)
    return item


def list_messages(session_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]

