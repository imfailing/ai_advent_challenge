"""
MCP-сервер поддержки: подключает JSON с пользователями и тикетами.

Инструменты дают ассистенту доступ к контексту пользователя/тикета:
  get_ticket(ticket_id)   — карточка тикета + данные пользователя
  get_user(user_id)       — профиль пользователя (тариф, устройства)
  list_tickets(status)    — список тикетов (по статусу или все)
"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA = Path(__file__).parent / "data" / "support.json"

mcp = FastMCP("support-server")


def _load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


@mcp.tool()
def get_ticket(ticket_id: str) -> dict:
    """
    Карточка тикета по ID (например 'T-1004') + данные пользователя (тариф и т.д.).
    """
    data = _load()
    t = data["tickets"].get(ticket_id)
    if not t:
        return {"error": f"Тикет {ticket_id} не найден"}
    user = data["users"].get(t["user_id"], {})
    return {**t, "user": user}


@mcp.tool()
def get_user(user_id: str) -> dict:
    """Профиль пользователя по ID (например 'U-1'): имя, email, тариф, устройства."""
    data = _load()
    u = data["users"].get(user_id)
    return u or {"error": f"Пользователь {user_id} не найден"}


@mcp.tool()
def list_tickets(status: str = "") -> list[dict]:
    """Список тикетов. status — 'open'/'closed'/пусто (все). Кратко: id, тема, тариф."""
    data = _load()
    out = []
    for t in data["tickets"].values():
        if status and t.get("status") != status:
            continue
        plan = data["users"].get(t["user_id"], {}).get("plan", "?")
        out.append({"id": t["id"], "subject": t["subject"],
                    "status": t["status"], "plan": plan})
    return out


if __name__ == "__main__":
    mcp.run()
