"""
MCP-сервер вокруг CRM API.

Каждый инструмент:
  • РЕГИСТРИРУЕТСЯ декоратором @mcp.tool();
  • ОПИСЫВАЕТ входные параметры через аннотации типов + docstring
    (FastMCP автоматически строит JSON-схему inputSchema);
  • ВОЗВРАЩАЕТ результат (dict/list), который сериализуется в ответ MCP.

Транспорт — stdio. Клиент/агент запускает этот файл подпроцессом.
"""

import crm_api
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("crm-server")


@mcp.tool()
def list_customers() -> list[dict]:
    """Вернуть список всех клиентов CRM: id, название, тариф (tier), MRR."""
    return crm_api.list_customers()


@mcp.tool()
def get_customer(customer_id: str) -> dict:
    """
    Получить полную карточку клиента по его ID.

    Параметры:
        customer_id: идентификатор клиента, например "C-001".
    """
    return crm_api.get_customer(customer_id)


@mcp.tool()
def search_deals(status: str = "") -> list[dict]:
    """
    Найти сделки, опционально отфильтровав по статусу.

    Параметры:
        status: "open", "won", "lost" или пусто (все сделки).
    """
    return crm_api.search_deals(status)


@mcp.tool()
def create_ticket(customer_id: str, subject: str, priority: str = "normal") -> dict:
    """
    Создать тикет поддержки для клиента и вернуть его карточку.

    Параметры:
        customer_id: ID клиента, например "C-002".
        subject:     тема обращения.
        priority:    "low", "normal" или "high" (по умолчанию "normal").
    """
    return crm_api.create_ticket(customer_id, subject, priority)


if __name__ == "__main__":
    mcp.run()
