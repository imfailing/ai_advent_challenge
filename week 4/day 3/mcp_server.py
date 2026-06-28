"""
MCP-сервер с периодическим/отложенным выполнением.

При старте поднимает фоновый планировщик (scheduler.py), который 24/7
собирает данные в SQLite. Инструменты MCP дают агенту доступ к:
  • агрегированной сводке за окно (summary);
  • снапшотам периодических сводок (recent_summaries);
  • отложенным напоминаниям (add_reminder / due_reminders);
  • статусу планировщика (scheduler_status).

Интервал сбора и частоту сводок можно задать через переменные окружения
SCHED_INTERVAL (сек, по умолчанию 1.0) и SCHED_SUMMARY_EVERY (тиков, 10).
"""

import os

import store
from mcp.server.fastmcp import FastMCP
from scheduler import Scheduler

# --- запускаем фоновый планировщик при старте сервера ---
store.init_db()
_scheduler = Scheduler(
    interval=float(os.environ.get("SCHED_INTERVAL", "1.0")),
    summary_every=int(os.environ.get("SCHED_SUMMARY_EVERY", "10")),
)
_scheduler.start()

mcp = FastMCP("scheduler-server")


@mcp.tool()
def summary(minutes: float = 5.0) -> dict:
    """
    Вернуть агрегированную сводку по собранной метрике за последние N минут.

    Параметры:
        minutes: размер окна в минутах (по умолчанию 5).
    Возвращает: count, avg, min, max, last и границы окна.
    """
    return store.summarize(minutes)


@mcp.tool()
def recent_summaries(limit: int = 5) -> list[dict]:
    """
    Вернуть последние периодические снапшоты сводок, которые планировщик
    сохраняет автоматически по расписанию.

    Параметры:
        limit: сколько последних снапшотов вернуть.
    """
    return store.recent_summaries(limit)


@mcp.tool()
def add_reminder(text: str, in_seconds: float) -> dict:
    """
    Поставить отложенное напоминание, которое «сработает» через in_seconds
    секунд (его обработает фоновый планировщик).

    Параметры:
        text:       текст напоминания.
        in_seconds: через сколько секунд оно должно сработать.
    """
    return store.add_reminder(text, in_seconds)


@mcp.tool()
def due_reminders() -> list[dict]:
    """Вернуть напоминания, которые уже сработали (наступил срок)."""
    return store.list_reminders(only="fired")


@mcp.tool()
def pending_reminders() -> list[dict]:
    """Вернуть напоминания, которые ещё ждут своего срока."""
    return store.list_reminders(only="pending")


@mcp.tool()
def scheduler_status() -> dict:
    """Состояние фонового планировщика: интервал, тики, число измерений."""
    return _scheduler.status()


if __name__ == "__main__":
    mcp.run()
