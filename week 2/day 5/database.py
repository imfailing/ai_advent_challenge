"""
Слой работы с SQLite.

Схема:
  sessions(id, created_at, updated_at, strategy, current_branch_id)
  messages(id, session_id, branch_id, role, content,
           prompt_tokens, completion_tokens, created_at)
  context_files(id, session_id, filename, content, size_chars, created_at)
  branches(id, session_id, name, forked_at_message_id, created_at)
    -- branch_id=NULL в messages означает основную ветку
  facts(id, session_id, key, value, updated_at)
    -- ключ-значение память для стратегии Sticky Facts
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
                id                TEXT    PRIMARY KEY,
                created_at        TEXT    NOT NULL,
                updated_at        TEXT    NOT NULL,
                strategy          TEXT    NOT NULL DEFAULT 'sliding_window',
                current_branch_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS messages (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        TEXT    NOT NULL REFERENCES sessions(id),
                branch_id         INTEGER,
                role              TEXT    NOT NULL,
                content           TEXT    NOT NULL,
                prompt_tokens     INTEGER,
                completion_tokens INTEGER,
                created_at        TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS context_files (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL REFERENCES sessions(id),
                filename   TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                size_chars INTEGER NOT NULL,
                created_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS branches (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id           TEXT    NOT NULL REFERENCES sessions(id),
                name                 TEXT    NOT NULL,
                forked_at_message_id INTEGER NOT NULL,
                created_at           TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS facts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                key        TEXT    NOT NULL,
                value      TEXT    NOT NULL,
                updated_at TEXT    NOT NULL,
                UNIQUE(session_id, key)
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


def get_strategy(session_id: str) -> str:
    with _conn() as con:
        row = con.execute(
            "SELECT strategy FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return row["strategy"] if row else "sliding_window"


def set_strategy(session_id: str, strategy: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE sessions SET strategy = ?, updated_at = ? WHERE id = ?",
            (strategy, _now(), session_id),
        )


def get_current_branch_id(session_id: str) -> int | None:
    with _conn() as con:
        row = con.execute(
            "SELECT current_branch_id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return row["current_branch_id"] if row else None


def set_current_branch_id(session_id: str, branch_id: int | None) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE sessions SET current_branch_id = ?, updated_at = ? WHERE id = ?",
            (branch_id, _now(), session_id),
        )


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------

def save_user_message(session_id: str, content: str,
                      branch_id: int | None = None) -> int:
    now = _now()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO messages (session_id, branch_id, role, content, created_at)"
            " VALUES (?, ?, 'user', ?, ?)",
            (session_id, branch_id, content, now),
        )
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        return cur.lastrowid


def save_assistant_message(session_id: str, content: str,
                           prompt_tokens: int, completion_tokens: int,
                           branch_id: int | None = None) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO messages"
            " (session_id, branch_id, role, content, prompt_tokens, completion_tokens, created_at)"
            " VALUES (?, ?, 'assistant', ?, ?, ?, ?)",
            (session_id, branch_id, content, prompt_tokens, completion_tokens, now),
        )
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))


def get_history(session_id: str, branch_id: int | None = None) -> list[dict]:
    """
    Полная история ветки в хронологическом порядке.
    branch_id=None → основная ветка.
    branch_id=X    → основная до точки форка + сообщения ветки X.
    """
    with _conn() as con:
        if branch_id is None:
            rows = con.execute(
                "SELECT role, content FROM messages"
                " WHERE session_id = ? AND branch_id IS NULL ORDER BY id",
                (session_id,),
            ).fetchall()
        else:
            branch = con.execute(
                "SELECT forked_at_message_id FROM branches WHERE id = ?",
                (branch_id,),
            ).fetchone()
            fork_id = branch["forked_at_message_id"] if branch else 0
            rows = con.execute(
                """
                SELECT id, role, content FROM messages
                 WHERE session_id = ? AND branch_id IS NULL AND id <= ?
                UNION ALL
                SELECT id, role, content FROM messages
                 WHERE session_id = ? AND branch_id = ?
                ORDER BY id
                """,
                (session_id, fork_id, session_id, branch_id),
            ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def get_last_message_id(session_id: str,
                        branch_id: int | None = None) -> int:
    """Id последнего сообщения в указанной ветке (0 если нет)."""
    with _conn() as con:
        if branch_id is None:
            row = con.execute(
                "SELECT MAX(id) FROM messages"
                " WHERE session_id = ? AND branch_id IS NULL",
                (session_id,),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT MAX(id) FROM messages"
                " WHERE session_id = ? AND branch_id = ?",
                (session_id, branch_id),
            ).fetchone()
    return row[0] or 0


def get_session_token_totals(session_id: str) -> dict:
    """Суммарные токены по всем веткам сессии."""
    with _conn() as con:
        row = con.execute(
            """
            SELECT COUNT(*)                             AS turns,
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


def clear_history(session_id: str) -> None:
    """Удалить сообщения, ветки, факты. Стратегию оставляем."""
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        con.execute("DELETE FROM branches WHERE session_id = ?", (session_id,))
        con.execute("DELETE FROM facts    WHERE session_id = ?", (session_id,))
        con.execute(
            "UPDATE sessions SET updated_at = ?, current_branch_id = NULL WHERE id = ?",
            (_now(), session_id),
        )


def list_sessions() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT s.id, s.created_at, s.updated_at, s.strategy,
                   COUNT(m.id)                          AS message_count,
                   COALESCE(SUM(m.prompt_tokens), 0)     AS total_prompt,
                   COALESCE(SUM(m.completion_tokens), 0) AS total_completion
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id ORDER BY s.updated_at DESC
            """,
        ).fetchall()
    return [
        {**dict(r), "total_cost_usd": _cost(r["total_prompt"], r["total_completion"])}
        for r in rows
    ]


# ------------------------------------------------------------------
# Branches
# ------------------------------------------------------------------

def create_branch(session_id: str, name: str,
                  forked_at_message_id: int) -> dict:
    now = _now()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO branches (session_id, name, forked_at_message_id, created_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, name, forked_at_message_id, now),
        )
        branch_id = cur.lastrowid
    return {"id": branch_id, "name": name,
            "forked_at_message_id": forked_at_message_id, "created_at": now}


def list_branches(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, name, forked_at_message_id, created_at"
            " FROM branches WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_branch(branch_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT id, session_id, name, forked_at_message_id, created_at"
            " FROM branches WHERE id = ?",
            (branch_id,),
        ).fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------------
# Facts (Sticky Facts strategy)
# ------------------------------------------------------------------

def load_facts(session_id: str) -> dict:
    with _conn() as con:
        rows = con.execute(
            "SELECT key, value FROM facts WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return {r["key"]: r["value"] for r in rows}


def save_facts(session_id: str, facts: dict) -> None:
    """Полностью заменить факты сессии."""
    now = _now()
    with _conn() as con:
        con.execute("DELETE FROM facts WHERE session_id = ?", (session_id,))
        for key, value in facts.items():
            con.execute(
                "INSERT INTO facts (session_id, key, value, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (session_id, str(key), str(value), now),
            )


# ------------------------------------------------------------------
# Context files
# ------------------------------------------------------------------

def save_context_file(session_id: str, filename: str, content: str) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO context_files"
            " (session_id, filename, content, size_chars, created_at)"
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


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

_PRICE_INPUT_PER_1M  = 0.14
_PRICE_OUTPUT_PER_1M = 0.28


def cost_usd(p: int, c: int) -> float:
    return round(p * _PRICE_INPUT_PER_1M / 1_000_000
                 + c * _PRICE_OUTPUT_PER_1M / 1_000_000, 6)


def _cost(p: int, c: int) -> float:
    return cost_usd(p, c)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
