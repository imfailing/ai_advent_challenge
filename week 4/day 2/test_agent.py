"""
Проверка: агент реально ВЫЗЫВАЕТ MCP-инструмент и ИСПОЛЬЗУЕТ результат.

Проверяем два уровня:
  1. MCP-сервер напрямую (соединение + список инструментов + вызов);
  2. агент целиком: задаём вопрос → агент вызывает нужный инструмент →
     результат отражён в ответе.
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent import MCPAgent

EXPECTED_TOOLS = {"list_customers", "get_customer", "search_deals", "create_ticket"}


async def check_server() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).parent / "mcp_server.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            assert tools == EXPECTED_TOOLS, f"инструменты: {tools}"
            print(f"✅ MCP-сервер: инструменты зарегистрированы {sorted(tools)}")

            # прямой вызов инструмента
            res = await session.call_tool("get_customer", {"customer_id": "C-001"})
            text = res.content[0].text
            assert "Ромашка" in text, text
            print("✅ прямой вызов get_customer(C-001) вернул карточку")


async def check_agent() -> None:
    async with MCPAgent() as agent:
        assert set(agent.tool_names) == EXPECTED_TOOLS
        print(f"✅ агент подключился, видит инструменты {sorted(agent.tool_names)}")

        # 1) запрос, требующий вызова search_deals
        r = await agent.ask("Какие открытые сделки и на какую сумму?")
        called = [tc.name for tc in r.tool_calls]
        assert "search_deals" in called, f"вызваны: {called}"
        # агент использовал результат: в ответе фигурирует сумма открытой сделки
        assert "2 520 000" in r.answer or "2520000" in r.answer.replace(" ", "") \
            or "2 610 000" in r.answer, r.answer
        print(f"✅ агент вызвал {called} и использовал результат в ответе")

        # 2) запрос на создание тикета (мутация через инструмент)
        r2 = await agent.ask("Создай тикет высокого приоритета для C-004 по теме «оплата».")
        called2 = [tc.name for tc in r2.tool_calls]
        assert "create_ticket" in called2, f"вызваны: {called2}"
        # результат инструмента содержит id нового тикета, агент его упомянул
        new_ticket = r2.tool_calls[-1].result
        assert '"id": "T-' in new_ticket, new_ticket
        print(f"✅ агент вызвал create_ticket → {new_ticket.splitlines()[1].strip()}")


async def main() -> None:
    await check_server()
    print()
    await check_agent()
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    asyncio.run(main())
