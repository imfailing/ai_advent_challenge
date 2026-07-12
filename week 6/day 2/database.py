"""SQLite: история диалога по сессиям (чтобы переживала перезагрузку страницы)."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "chat.db"


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")


def add_message(session_id: str, role: str, content: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now(timezone.utc).isoformat()))


def get_messages(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def clear(session_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
