"""
SQLite: история диалога + ПАМЯТЬ ЗАДАЧИ (task state).

  sessions(id, created_at, updated_at)
  messages(id, session_id, role, content, sources, created_at)
    sources — JSON списка источников для ответов ассистента
  task_memory(session_id, goal, clarifications, constraints, terms, updated_at)
    goal          — цель диалога (строка)
    clarifications— что пользователь уже уточнил (JSON-список)
    constraints   — зафиксированные ограничения (JSON-список)
    terms         — зафиксированные термины/определения (JSON-объект)
"""

import json
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
        con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                sources    TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS task_memory (
                session_id     TEXT PRIMARY KEY,
                goal           TEXT DEFAULT '',
                clarifications TEXT DEFAULT '[]',
                constraints    TEXT DEFAULT '[]',
                terms          TEXT DEFAULT '{}',
                updated_at     TEXT NOT NULL
            );
        """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------
# Sessions / messages
# ------------------------------------------------------------------

def ensure_session(session_id: str) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(id) DO NOTHING", (session_id, now, now))
        con.execute(
            "INSERT INTO task_memory (session_id, updated_at) VALUES (?, ?)"
            " ON CONFLICT(session_id) DO NOTHING", (session_id, now))


def add_message(session_id: str, role: str, content: str,
                sources: list | None = None) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content, sources, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content,
             json.dumps(sources, ensure_ascii=False) if sources is not None else None, now))
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))


def get_messages(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content, sources FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,)).fetchall()
    out = []
    for r in rows:
        out.append({"role": r["role"], "content": r["content"],
                    "sources": json.loads(r["sources"]) if r["sources"] else []})
    return out


def clear_session(session_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        con.execute(
            "UPDATE task_memory SET goal='', clarifications='[]', constraints='[]',"
            " terms='{}', updated_at=? WHERE session_id=?", (_now(), session_id))


# ------------------------------------------------------------------
# Task memory
# ------------------------------------------------------------------

def get_task_memory(session_id: str) -> dict:
    with _conn() as con:
        row = con.execute(
            "SELECT goal, clarifications, constraints, terms FROM task_memory"
            " WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        return {"goal": "", "clarifications": [], "constraints": [], "terms": {}}
    return {
        "goal":           row["goal"] or "",
        "clarifications": json.loads(row["clarifications"] or "[]"),
        "constraints":    json.loads(row["constraints"] or "[]"),
        "terms":          json.loads(row["terms"] or "{}"),
    }


def set_task_memory(session_id: str, memory: dict) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE task_memory SET goal=?, clarifications=?, constraints=?, terms=?,"
            " updated_at=? WHERE session_id=?",
            (memory.get("goal", ""),
             json.dumps(memory.get("clarifications", []), ensure_ascii=False),
             json.dumps(memory.get("constraints", []), ensure_ascii=False),
             json.dumps(memory.get("terms", {}), ensure_ascii=False),
             _now(), session_id))
