"""
Минимальный MCP-сервер для демонстрации.

Поднимает несколько простых инструментов (tools), которые клиент сможет
обнаружить через list_tools(). Сервер общается по stdio — стандартный
транспорт MCP для локального запуска дочерним процессом.

Запуск напрямую не требуется: клиент (client.py) сам стартует этот файл
как подпроцесс и подключается к нему.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-server")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Сложить два числа и вернуть сумму."""
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Перемножить два числа и вернуть произведение."""
    return a * b


@mcp.tool()
def echo(text: str) -> str:
    """Вернуть переданный текст без изменений."""
    return text


@mcp.tool()
def reverse(text: str) -> str:
    """Развернуть строку задом наперёд."""
    return text[::-1]


if __name__ == "__main__":
    # По умолчанию FastMCP.run() использует stdio-транспорт.
    mcp.run()
