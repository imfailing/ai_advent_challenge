"""
Mock CRM API — изображает внешний сервис (как Яндекс.Трекер / CRM / Git API).

Данные в памяти, чтобы пример был самодостаточным и детерминированным.
MCP-сервер (mcp_server.py) оборачивает эти функции в инструменты.
"""

from datetime import datetime, timezone

# ------------------------------------------------------------------
# «База данных» CRM
# ------------------------------------------------------------------

_CUSTOMERS = {
    "C-001": {"id": "C-001", "name": "ООО «Ромашка»",   "tier": "gold",
              "mrr": 120_000, "owner": "Иванов",  "city": "Москва"},
    "C-002": {"id": "C-002", "name": "ИП Петров",        "tier": "silver",
              "mrr": 35_000,  "owner": "Сидорова", "city": "Казань"},
    "C-003": {"id": "C-003", "name": "АО «ТехноСила»",   "tier": "gold",
              "mrr": 210_000, "owner": "Иванов",  "city": "Санкт-Петербург"},
    "C-004": {"id": "C-004", "name": "ООО «Старт»",      "tier": "bronze",
              "mrr": 8_000,   "owner": "Сидорова", "city": "Новосибирск"},
}

_DEALS = [
    {"id": "D-100", "customer_id": "C-001", "title": "Продление подписки",
     "amount": 1_440_000, "status": "won"},
    {"id": "D-101", "customer_id": "C-003", "title": "Расширение лицензий",
     "amount": 2_520_000, "status": "open"},
    {"id": "D-102", "customer_id": "C-002", "title": "Пилотный проект",
     "amount": 90_000,    "status": "open"},
    {"id": "D-103", "customer_id": "C-004", "title": "Базовый тариф",
     "amount": 96_000,    "status": "lost"},
]

_TICKETS: list[dict] = []
_TICKET_SEQ = 500


# ------------------------------------------------------------------
# «Эндпоинты» API
# ------------------------------------------------------------------

def list_customers() -> list[dict]:
    """Список всех клиентов (краткая карточка)."""
    return [{"id": c["id"], "name": c["name"], "tier": c["tier"], "mrr": c["mrr"]}
            for c in _CUSTOMERS.values()]


def get_customer(customer_id: str) -> dict:
    """Полная карточка клиента по ID. ValueError, если не найден."""
    c = _CUSTOMERS.get(customer_id)
    if not c:
        raise ValueError(f"Клиент {customer_id!r} не найден")
    return dict(c)


def search_deals(status: str = "") -> list[dict]:
    """Сделки, опционально отфильтрованные по статусу (open|won|lost)."""
    status = (status or "").strip().lower()
    if status and status not in ("open", "won", "lost"):
        raise ValueError("status должен быть open, won, lost или пустым")
    return [d for d in _DEALS if not status or d["status"] == status]


def create_ticket(customer_id: str, subject: str, priority: str = "normal") -> dict:
    """Создать тикет поддержки для клиента. priority: low|normal|high."""
    if customer_id not in _CUSTOMERS:
        raise ValueError(f"Клиент {customer_id!r} не найден")
    priority = (priority or "normal").strip().lower()
    if priority not in ("low", "normal", "high"):
        raise ValueError("priority должен быть low, normal или high")
    global _TICKET_SEQ
    _TICKET_SEQ += 1
    ticket = {
        "id":          f"T-{_TICKET_SEQ}",
        "customer_id": customer_id,
        "subject":     subject,
        "priority":    priority,
        "status":      "open",
        "created_at":  datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _TICKETS.append(ticket)
    return ticket
