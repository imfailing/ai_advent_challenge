"""
Слой работы с SQLite — хранение и загрузка истории диалогов.

Схема:
  sessions(id TEXT PK, created_at, updated_at)
  messages(id INTEGER PK, session_id FK, role, content, created_at)

Агент работает только с этим модулем — Flask и LLM ничего не знают о БД.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "history.db"


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
    """Создать таблицы, если их ещё нет."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                role       TEXT NOT NULL,   -- 'user' | 'assistant'
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)


def ensure_session(session_id: str) -> None:
    """Создать запись сессии, если её нет."""
    now = _now()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO sessions (id, created_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (session_id, now, now),
        )


def save_message(session_id: str, role: str, content: str) -> None:
    """Записать одно сообщение и обновить updated_at сессии."""
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        con.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )


def load_history(session_id: str) -> list[dict]:
    """Загрузить всю историю сообщений сессии в формате [{role, content}, ...]."""
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def clear_history(session_id: str) -> None:
    """Удалить все сообщения сессии (сессия остаётся в таблице)."""
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        con.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (_now(), session_id),
        )


def list_sessions() -> list[dict]:
    """Вернуть список всех сессий с количеством сообщений."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT s.id, s.created_at, s.updated_at,
                   COUNT(m.id) AS message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            """,
        ).fetchall()
    return [dict(r) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
