"""
Слой работы с SQLite.

Схема:
  sessions(id, created_at, updated_at)
  messages(id, session_id, role, content,
           prompt_tokens, completion_tokens,
           created_at)
  context_files(id, session_id, filename, content, size_chars, created_at)
  summaries(id, session_id, content,
            from_message_id, to_message_id, message_count,
            created_at)
    -- каждая строка — сжатое резюме пачки сообщений;
    -- подставляется в запрос вместо полной истории.
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
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        TEXT NOT NULL REFERENCES sessions(id),
                role              TEXT NOT NULL,
                content           TEXT NOT NULL,
                prompt_tokens     INTEGER,
                completion_tokens INTEGER,
                created_at        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS context_files (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                filename   TEXT NOT NULL,
                content    TEXT NOT NULL,
                size_chars INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS summaries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT    NOT NULL REFERENCES sessions(id),
                content         TEXT    NOT NULL,
                from_message_id INTEGER NOT NULL,
                to_message_id   INTEGER NOT NULL,
                message_count   INTEGER NOT NULL,
                created_at      TEXT    NOT NULL
            );
        """)


def ensure_session(session_id: str) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(id) DO NOTHING",
            (session_id, now, now),
        )


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------

def save_user_message(session_id: str, content: str) -> int:
    """Сохранить сообщение пользователя, вернуть его id."""
    now = _now()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, 'user', ?, ?)",
            (session_id, content, now),
        )
        con.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        return cur.lastrowid


def save_assistant_message(
    session_id: str,
    content: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO messages"
            " (session_id, role, content, prompt_tokens, completion_tokens, created_at)"
            " VALUES (?, 'assistant', ?, ?, ?, ?)",
            (session_id, content, prompt_tokens, completion_tokens, now),
        )
        con.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )


def get_messages_after(session_id: str, after_id: int) -> list[dict]:
    """Все сообщения с id > after_id (то есть ещё не покрытые суммари)."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, role, content FROM messages"
            " WHERE session_id = ? AND id > ? ORDER BY id",
            (session_id, after_id),
        ).fetchall()
    return [{"id": r["id"], "role": r["role"], "content": r["content"]} for r in rows]


def get_recent_messages(session_id: str, limit: int) -> list[dict]:
    """Последние N сообщений в хронологическом порядке."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, role, content FROM messages"
            " WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [{"id": r["id"], "role": r["role"], "content": r["content"]}
            for r in reversed(rows)]


def get_total_message_count(session_id: str) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
    return row[0]


def get_session_token_totals(session_id: str) -> dict:
    with _conn() as con:
        row = con.execute(
            """
            SELECT
                COUNT(*)                            AS turns,
                COALESCE(SUM(prompt_tokens), 0)     AS total_prompt,
                COALESCE(SUM(completion_tokens), 0) AS total_completion
            FROM messages
            WHERE session_id = ? AND role = 'assistant'
            """,
            (session_id,),
        ).fetchone()
    total_prompt     = row["total_prompt"]
    total_completion = row["total_completion"]
    return {
        "turns":            row["turns"],
        "total_prompt":     total_prompt,
        "total_completion": total_completion,
        "total_tokens":     total_prompt + total_completion,
        "total_cost_usd":   _cost(total_prompt, total_completion),
    }


def clear_history(session_id: str) -> None:
    """Удалить все сообщения и все суммари сессии."""
    with _conn() as con:
        con.execute("DELETE FROM messages  WHERE session_id = ?", (session_id,))
        con.execute("DELETE FROM summaries WHERE session_id = ?", (session_id,))
        con.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
        )


def list_sessions() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT s.id, s.created_at, s.updated_at,
                   COUNT(m.id)                          AS message_count,
                   COALESCE(SUM(m.prompt_tokens), 0)     AS total_prompt,
                   COALESCE(SUM(m.completion_tokens), 0) AS total_completion
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            """,
        ).fetchall()
    return [
        {**dict(r), "total_cost_usd": _cost(r["total_prompt"], r["total_completion"])}
        for r in rows
    ]


# ------------------------------------------------------------------
# Summaries
# ------------------------------------------------------------------

def get_last_summarized_message_id(session_id: str) -> int:
    """Id последнего сообщения, покрытого суммари. 0 если суммари нет."""
    with _conn() as con:
        row = con.execute(
            "SELECT MAX(to_message_id) FROM summaries WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return row[0] or 0


def save_summary(
    session_id: str,
    content: str,
    from_id: int,
    to_id: int,
    message_count: int,
) -> int:
    """Сохранить суммари, вернуть его id."""
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO summaries"
            " (session_id, content, from_message_id, to_message_id, message_count, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, content, from_id, to_id, message_count, _now()),
        )
        return cur.lastrowid


def load_summaries(session_id: str) -> list[dict]:
    """Все суммари сессии в хронологическом порядке."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, content, from_message_id, to_message_id, message_count, created_at"
            " FROM summaries WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------
# Context files
# ------------------------------------------------------------------

def save_context_file(session_id: str, filename: str, content: str) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO context_files (session_id, filename, content, size_chars, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, filename, content, len(content), _now()),
        )
        return cur.lastrowid


def load_context_files(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, filename, content, size_chars, created_at"
            " FROM context_files WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_context_file(file_id: int, session_id: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM context_files WHERE id = ? AND session_id = ?",
            (file_id, session_id),
        )
    return cur.rowcount > 0


def clear_context_files(session_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM context_files WHERE session_id = ?", (session_id,))


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

_PRICE_INPUT_PER_1M  = 0.14   # USD за 1M входных токенов (deepseek-v4-flash, cache miss)
_PRICE_OUTPUT_PER_1M = 0.28   # USD за 1M выходных токенов


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        prompt_tokens     * _PRICE_INPUT_PER_1M  / 1_000_000
        + completion_tokens * _PRICE_OUTPUT_PER_1M / 1_000_000,
        6,
    )


def _cost(p: int, c: int) -> float:
    return cost_usd(p, c)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
