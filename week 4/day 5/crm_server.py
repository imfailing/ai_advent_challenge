"""
MCP-сервер №1 — CRM. Инструменты для данных о клиентах и сделках.
Самодостаточен: данные в памяти.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("crm-server")

_CUSTOMERS = {
    "C-001": {"id": "C-001", "name": "ООО «Ромашка»", "tier": "gold",  "owner": "Иванов"},
    "C-002": {"id": "C-002", "name": "ИП Петров",      "tier": "silver", "owner": "Сидорова"},
    "C-003": {"id": "C-003", "name": "АО «ТехноСила»", "tier": "gold",  "owner": "Иванов"},
}
_DEALS = [
    {"id": "D-100", "customer_id": "C-001", "title": "Продление подписки", "amount": 1_440_000, "status": "won"},
    {"id": "D-101", "customer_id": "C-003", "title": "Расширение лицензий", "amount": 2_520_000, "status": "open"},
    {"id": "D-102", "customer_id": "C-003", "title": "Доп. модуль аналитики", "amount": 480_000, "status": "open"},
]


@mcp.tool()
def get_customer(customer_id: str) -> dict:
    """Получить карточку клиента по ID (например 'C-003')."""
    c = _CUSTOMERS.get(customer_id)
    if not c:
        raise ValueError(f"Клиент {customer_id!r} не найден")
    return dict(c)


@mcp.tool()
def search_deals(customer_id: str = "", status: str = "") -> list[dict]:
    """Найти сделки по клиенту и/или статусу (open|won|lost). Пусто = все."""
    res = _DEALS
    if customer_id:
        res = [d for d in res if d["customer_id"] == customer_id]
    if status:
        res = [d for d in res if d["status"] == status]
    return list(res)


if __name__ == "__main__":
    mcp.run()
