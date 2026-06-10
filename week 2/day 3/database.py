"""
Слой работы с SQLite.

Схема:
  sessions(id, created_at, updated_at)
  messages(id, session_id, role, content,
           prompt_tokens, completion_tokens,  -- заполняются только для role='assistant'
           created_at)

Функции агрегации токенов позволяют считать стоимость как за отдельный
запрос, так и накопленным итогом по всей истории сессии.
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
                prompt_tokens     INTEGER,       -- входные токены (только для assistant)
                completion_tokens INTEGER,       -- выходные токены (только для assistant)
                created_at        TEXT NOT NULL
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


def save_user_message(session_id: str, content: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, 'user', ?, ?)",
            (session_id, content, _now()),
        )
        con.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
        )


def save_assistant_message(
    session_id: str,
    content: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO messages"
            " (session_id, role, content, prompt_tokens, completion_tokens, created_at)"
            " VALUES (?, 'assistant', ?, ?, ?, ?)",
            (session_id, content, prompt_tokens, completion_tokens, _now()),
        )
        con.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
        )


def load_history(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def get_session_token_totals(session_id: str) -> dict:
    """Суммарные токены и стоимость по всей истории сессии."""
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
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
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
# Pricing (DeepSeek deepseek-chat, cache-miss, as of 2025)
# ------------------------------------------------------------------
_PRICE_INPUT_PER_1M  = 0.27   # USD за 1M входных токенов
_PRICE_OUTPUT_PER_1M = 1.10   # USD за 1M выходных токенов


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    """Рассчитать стоимость запроса в USD."""
    return round(
        prompt_tokens  * _PRICE_INPUT_PER_1M  / 1_000_000
        + completion_tokens * _PRICE_OUTPUT_PER_1M / 1_000_000,
        6,
    )


def _cost(prompt_tokens: int, completion_tokens: int) -> float:
    return cost_usd(prompt_tokens, completion_tokens)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
