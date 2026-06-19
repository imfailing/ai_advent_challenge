"""
Слой работы с SQLite. Три типа памяти хранятся в РАЗНЫХ таблицах —
это и есть «явная модель памяти».

Схема:
  sessions(id, created_at, updated_at, active_task)

  # КРАТКОСРОЧНАЯ память — текущий диалог
  messages(id, session_id, role, content,
           prompt_tokens, completion_tokens, created_at)

  # РАБОЧАЯ память — данные текущей задачи (key-value, привязаны к задаче)
  working_memory(id, session_id, task, key, value, updated_at,
                 UNIQUE(session_id, key))

  # ДОЛГОВРЕМЕННАЯ память — профиль / решения / знания (переживает очистку диалога)
  long_term_memory(id, session_id, category, content, created_at,
                   UNIQUE(session_id, category, content))
    category ∈ {'profile', 'decision', 'knowledge'}
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "history.db"

LONG_TERM_CATEGORIES = ("profile", "decision", "knowledge")


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
                id          TEXT PRIMARY KEY,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                active_task TEXT
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

            CREATE TABLE IF NOT EXISTS working_memory (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                task       TEXT,
                key        TEXT NOT NULL,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(session_id, key)
            );

            CREATE TABLE IF NOT EXISTS long_term_memory (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                category   TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(session_id, category, content)
            );
        """)


# ------------------------------------------------------------------
# Sessions
# ------------------------------------------------------------------

def ensure_session(session_id: str) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(id) DO NOTHING",
            (session_id, now, now),
        )


def get_active_task(session_id: str) -> str | None:
    with _conn() as con:
        row = con.execute(
            "SELECT active_task FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return row["active_task"] if row else None


def set_active_task(session_id: str, task: str | None) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE sessions SET active_task = ?, updated_at = ? WHERE id = ?",
            (task, _now(), session_id),
        )


# ------------------------------------------------------------------
# КРАТКОСРОЧНАЯ память — messages
# ------------------------------------------------------------------

def save_user_message(session_id: str, content: str) -> int:
    now = _now()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, 'user', ?, ?)",
            (session_id, content, now),
        )
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        return cur.lastrowid


def save_assistant_message(session_id: str, content: str,
                           prompt_tokens: int, completion_tokens: int) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO messages"
            " (session_id, role, content, prompt_tokens, completion_tokens, created_at)"
            " VALUES (?, 'assistant', ?, ?, ?, ?)",
            (session_id, content, prompt_tokens, completion_tokens, now),
        )
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))


def get_messages(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def clear_short_term(session_id: str) -> None:
    """Очистить только диалог. Рабочая и долговременная память не трогаются."""
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (_now(), session_id))


# ------------------------------------------------------------------
# РАБОЧАЯ память — working_memory
# ------------------------------------------------------------------

def upsert_working(session_id: str, key: str, value: str,
                   task: str | None = None) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO working_memory (session_id, task, key, value, updated_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(session_id, key) DO UPDATE SET"
            "   value = excluded.value, task = excluded.task, updated_at = excluded.updated_at",
            (session_id, task, str(key), str(value), now),
        )


def load_working(session_id: str) -> dict:
    with _conn() as con:
        rows = con.execute(
            "SELECT key, value FROM working_memory WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return {r["key"]: r["value"] for r in rows}


def delete_working_key(session_id: str, key: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM working_memory WHERE session_id = ? AND key = ?",
            (session_id, key),
        )
    return cur.rowcount > 0


def clear_working(session_id: str) -> None:
    """Очистить рабочую память (например, при завершении/смене задачи)."""
    with _conn() as con:
        con.execute("DELETE FROM working_memory WHERE session_id = ?", (session_id,))


# ------------------------------------------------------------------
# ДОЛГОВРЕМЕННАЯ память — long_term_memory
# ------------------------------------------------------------------

def add_long_term(session_id: str, category: str, content: str) -> bool:
    """Добавить запись. Возвращает True, если запись новая (не дубль)."""
    if category not in LONG_TERM_CATEGORIES:
        raise ValueError(f"Неизвестная категория: {category!r}")
    content = content.strip()
    if not content:
        return False
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO long_term_memory (session_id, category, content, created_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(session_id, category, content) DO NOTHING",
            (session_id, category, content, _now()),
        )
    return cur.rowcount > 0


def load_long_term(session_id: str) -> dict:
    """Вернуть {category: [content, ...]} по всем категориям."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, category, content FROM long_term_memory"
            " WHERE session_id = ? ORDER BY category, id",
            (session_id,),
        ).fetchall()
    out: dict[str, list[dict]] = {c: [] for c in LONG_TERM_CATEGORIES}
    for r in rows:
        out.setdefault(r["category"], []).append({"id": r["id"], "content": r["content"]})
    return out


def delete_long_term(entry_id: int, session_id: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM long_term_memory WHERE id = ? AND session_id = ?",
            (entry_id, session_id),
        )
    return cur.rowcount > 0


def clear_long_term(session_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM long_term_memory WHERE session_id = ?", (session_id,))


# ------------------------------------------------------------------
# Токены / стоимость сессии
# ------------------------------------------------------------------

def get_session_token_totals(session_id: str) -> dict:
    with _conn() as con:
        row = con.execute(
            """
            SELECT COUNT(*)                            AS turns,
                   COALESCE(SUM(prompt_tokens), 0)     AS total_prompt,
                   COALESCE(SUM(completion_tokens), 0) AS total_completion
            FROM messages WHERE session_id = ? AND role = 'assistant'
            """,
            (session_id,),
        ).fetchone()
    tp, tc = row["total_prompt"], row["total_completion"]
    return {
        "turns":            row["turns"],
        "total_prompt":     tp,
        "total_completion": tc,
        "total_tokens":     tp + tc,
        "total_cost_usd":   _cost(tp, tc),
    }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

_PRICE_INPUT_PER_1M  = 0.14
_PRICE_OUTPUT_PER_1M = 0.28


def _cost(p: int, c: int) -> float:
    return round(p * _PRICE_INPUT_PER_1M / 1_000_000
                 + c * _PRICE_OUTPUT_PER_1M / 1_000_000, 6)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
