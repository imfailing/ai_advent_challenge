"""
Слой работы с SQLite. Память (day 1) + жизненный цикл задачи с ГЕЙТАМИ (day 5).

Состояние задачи:
  task_state(session_id, task_name, stage, current_step, expected_action,
             status, conditions, created_at, updated_at)
    conditions — JSON булевых гейтов: {"plan_approved": true, ...}
  task_transitions(id, session_id, from_stage, to_stage, accepted, note, created_at)
    accepted=0 — отклонённая попытка перехода (для истории)
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import statemachine as sm

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

            CREATE TABLE IF NOT EXISTS task_state (
                session_id      TEXT PRIMARY KEY REFERENCES sessions(id),
                task_name       TEXT,
                stage           TEXT NOT NULL,
                current_step    TEXT DEFAULT '',
                expected_action TEXT DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'active',
                conditions      TEXT NOT NULL DEFAULT '{}',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_transitions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                from_stage TEXT,
                to_stage   TEXT NOT NULL,
                accepted   INTEGER NOT NULL DEFAULT 1,
                note       TEXT DEFAULT '',
                created_at TEXT NOT NULL
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


def set_active_task(session_id: str, task: str | None) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE sessions SET active_task = ?, updated_at = ? WHERE id = ?",
            (task, _now(), session_id),
        )


# ------------------------------------------------------------------
# Состояние задачи (с гейтами)
# ------------------------------------------------------------------

def _row_to_state(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    try:
        d["conditions"] = json.loads(d.get("conditions") or "{}")
    except json.JSONDecodeError:
        d["conditions"] = {}
    return d


def get_task_state(session_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM task_state WHERE session_id = ?", (session_id,)
        ).fetchone()
    return _row_to_state(row)


def start_task(session_id: str, task_name: str,
               current_step: str = "", expected_action: str = "") -> dict:
    now = _now()
    conditions = json.dumps({g: False for g in sm.GATES})
    with _conn() as con:
        con.execute(
            """INSERT INTO task_state
               (session_id, task_name, stage, current_step, expected_action,
                status, conditions, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 task_name = excluded.task_name, stage = excluded.stage,
                 current_step = excluded.current_step,
                 expected_action = excluded.expected_action,
                 status = 'active', conditions = excluded.conditions,
                 updated_at = excluded.updated_at""",
            (session_id, task_name, sm.INITIAL_STAGE, current_step,
             expected_action, conditions, now, now),
        )
        con.execute(
            "INSERT INTO task_transitions (session_id, from_stage, to_stage, accepted, note, created_at)"
            " VALUES (?, NULL, ?, 1, ?, ?)",
            (session_id, sm.INITIAL_STAGE, f"старт задачи: {task_name}", now),
        )
    return get_task_state(session_id)


def update_task_fields(session_id: str, *, current_step: str | None = None,
                       expected_action: str | None = None) -> dict | None:
    sets, params = [], []
    if current_step is not None:
        sets.append("current_step = ?");    params.append(current_step)
    if expected_action is not None:
        sets.append("expected_action = ?"); params.append(expected_action)
    if not sets:
        return get_task_state(session_id)
    sets.append("updated_at = ?"); params.append(_now())
    params.append(session_id)
    with _conn() as con:
        con.execute(f"UPDATE task_state SET {', '.join(sets)} WHERE session_id = ?", params)
    return get_task_state(session_id)


def set_condition(session_id: str, gate: str, value: bool) -> dict | None:
    state = get_task_state(session_id)
    if not state:
        return None
    conds = state["conditions"]
    conds[gate] = bool(value)
    with _conn() as con:
        con.execute(
            "UPDATE task_state SET conditions = ?, updated_at = ? WHERE session_id = ?",
            (json.dumps(conds), _now(), session_id),
        )
    return get_task_state(session_id)


def transition_stage(session_id: str, to_stage: str, note: str = "") -> dict:
    """Безусловная запись перехода (валидация — на стороне agent.py)."""
    now = _now()
    cur = get_task_state(session_id)
    from_stage = cur["stage"] if cur else None
    with _conn() as con:
        con.execute(
            "UPDATE task_state SET stage = ?, updated_at = ? WHERE session_id = ?",
            (to_stage, now, session_id),
        )
        con.execute(
            "INSERT INTO task_transitions (session_id, from_stage, to_stage, accepted, note, created_at)"
            " VALUES (?, ?, ?, 1, ?, ?)",
            (session_id, from_stage, to_stage, note, now),
        )
    return get_task_state(session_id)


def log_rejected_transition(session_id: str, from_stage: str | None,
                            to_stage: str, reason: str) -> None:
    """Записать ОТКЛОНЁННУЮ попытку перехода (для истории/отладки)."""
    with _conn() as con:
        con.execute(
            "INSERT INTO task_transitions (session_id, from_stage, to_stage, accepted, note, created_at)"
            " VALUES (?, ?, ?, 0, ?, ?)",
            (session_id, from_stage, to_stage, reason, _now()),
        )


def set_task_status(session_id: str, status: str) -> dict | None:
    with _conn() as con:
        con.execute(
            "UPDATE task_state SET status = ?, updated_at = ? WHERE session_id = ?",
            (status, _now(), session_id),
        )
    return get_task_state(session_id)


def get_transitions(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT from_stage, to_stage, accepted, note, created_at FROM task_transitions"
            " WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def reset_task(session_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM task_state WHERE session_id = ?", (session_id,))
        con.execute("DELETE FROM task_transitions WHERE session_id = ?", (session_id,))


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
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (_now(), session_id))


# ------------------------------------------------------------------
# РАБОЧАЯ память
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


# ------------------------------------------------------------------
# ДОЛГОВРЕМЕННАЯ память
# ------------------------------------------------------------------

def add_long_term(session_id: str, category: str, content: str) -> bool:
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


# ------------------------------------------------------------------
# Токены / стоимость
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
