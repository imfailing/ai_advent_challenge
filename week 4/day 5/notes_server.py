"""
MCP-сервер №3 — Заметки. Сохранение и чтение заметок (JSON-файл).
Самодостаточен: хранилище — notes.json рядом.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notes-server")

NOTES_PATH = Path(__file__).parent / "notes.json"


def _load() -> list[dict]:
    if NOTES_PATH.exists():
        return json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    return []


def _save(notes: list[dict]) -> None:
    NOTES_PATH.write_text(json.dumps(notes, ensure_ascii=False, indent=2),
                          encoding="utf-8")


@mcp.tool()
def save_note(title: str, content: str) -> dict:
    """Сохранить заметку (тема + текст). Возвращает её карточку с id."""
    notes = _load()
    note = {
        "id":         f"N-{len(notes) + 1}",
        "title":      title,
        "content":    content,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    notes.append(note)
    _save(notes)
    return note


@mcp.tool()
def list_notes() -> list[dict]:
    """Вернуть все сохранённые заметки (id, title, created_at)."""
    return [{"id": n["id"], "title": n["title"], "created_at": n["created_at"]}
            for n in _load()]


if __name__ == "__main__":
    mcp.run()
