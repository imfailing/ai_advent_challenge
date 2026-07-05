"""
Хранилище SQLite для периодического инструмента.

Таблицы:
  samples(id, metric, value, ts)          — собранные измерения
  reminders(id, text, due_ts, fired, ...) — отложенные напоминания
  summaries(id, win_start, win_end, count, avg, min, max, ts) — снапшоты сводок

Все операции открывают своё соединение — безопасно для фонового потока
планировщика и потока MCP-сервера одновременно.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "scheduler.db"


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH, timeout=5)
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
            CREATE TABLE IF NOT EXISTS samples (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT NOT NULL,
                value  REAL NOT NULL,
                ts     REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT NOT NULL,
                due_ts     REAL NOT NULL,
                fired      INTEGER NOT NULL DEFAULT 0,
                created_ts REAL NOT NULL,
                fired_ts   REAL
            );
            CREATE TABLE IF NOT EXISTS summaries (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                metric    TEXT NOT NULL,
                win_start REAL NOT NULL,
                win_end   REAL NOT NULL,
                count     INTEGER NOT NULL,
                avg       REAL,
                min       REAL,
                max       REAL,
                ts        REAL NOT NULL
            );
        """)


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------
# Samples
# ------------------------------------------------------------------

def add_sample(metric: str, value: float) -> None:
    with _conn() as con:
        con.execute("INSERT INTO samples (metric, value, ts) VALUES (?, ?, ?)",
                    (metric, value, _now()))


def summarize(minutes: float = 5.0, metric: str = "active_users") -> dict:
    """Агрегировать измерения за последние `minutes` минут."""
    cutoff = _now() - minutes * 60
    with _conn() as con:
        rows = con.execute(
            "SELECT value, ts FROM samples WHERE metric = ? AND ts >= ? ORDER BY ts",
            (metric, cutoff),
        ).fetchall()
    vals = [r["value"] for r in rows]
    if not vals:
        return {"metric": metric, "window_minutes": minutes, "count": 0,
                "avg": None, "min": None, "max": None, "last": None,
                "from": None, "to": None}
    return {
        "metric":         metric,
        "window_minutes": minutes,
        "count":          len(vals),
        "avg":            round(sum(vals) / len(vals), 2),
        "min":            min(vals),
        "max":            max(vals),
        "last":           vals[-1],
        "from":           _iso(rows[0]["ts"]),
        "to":             _iso(rows[-1]["ts"]),
    }


def sample_count() -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) AS n FROM samples").fetchone()["n"]


# ------------------------------------------------------------------
# Reminders (отложенное выполнение)
# ------------------------------------------------------------------

def add_reminder(text: str, in_seconds: float) -> dict:
    now = _now()
    due = now + max(0.0, in_seconds)
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO reminders (text, due_ts, created_ts) VALUES (?, ?, ?)",
            (text, due, now),
        )
        rid = cur.lastrowid
    return {"id": rid, "text": text, "due_at": _iso(due), "fired": False}


def fire_due_reminders() -> list[dict]:
    """Пометить наступившие напоминания сработавшими. Возвращает их."""
    now = _now()
    with _conn() as con:
        rows = con.execute(
            "SELECT id, text, due_ts FROM reminders WHERE fired = 0 AND due_ts <= ?",
            (now,),
        ).fetchall()
        for r in rows:
            con.execute("UPDATE reminders SET fired = 1, fired_ts = ? WHERE id = ?",
                        (now, r["id"]))
    return [{"id": r["id"], "text": r["text"], "due_at": _iso(r["due_ts"])}
            for r in rows]


def list_reminders(only: str = "all") -> list[dict]:
    """only: all | pending | fired."""
    q = "SELECT id, text, due_ts, fired, fired_ts FROM reminders"
    if only == "pending":
        q += " WHERE fired = 0"
    elif only == "fired":
        q += " WHERE fired = 1"
    q += " ORDER BY due_ts"
    with _conn() as con:
        rows = con.execute(q).fetchall()
    return [{"id": r["id"], "text": r["text"], "due_at": _iso(r["due_ts"]),
             "fired": bool(r["fired"]), "fired_at": _iso(r["fired_ts"])}
            for r in rows]


# ------------------------------------------------------------------
# Summaries (периодические снапшоты)
# ------------------------------------------------------------------

def add_summary_snapshot(s: dict) -> None:
    if s["count"] == 0:
        return
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO summaries (metric, win_start, win_end, count, avg, min, max, ts)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (s["metric"], now - s["window_minutes"] * 60, now,
             s["count"], s["avg"], s["min"], s["max"], now),
        )


def recent_summaries(limit: int = 5) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT metric, count, avg, min, max, ts FROM summaries"
            " ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [{"metric": r["metric"], "count": r["count"], "avg": r["avg"],
             "min": r["min"], "max": r["max"], "at": _iso(r["ts"])}
            for r in rows]
