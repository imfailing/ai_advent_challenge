"""
Проверка MCP-клиента: соединение устанавливается и список инструментов
возвращается корректно. Запускает локальный server.py как подпроцесс.
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {"add", "multiply", "echo", "reverse"}


async def run() -> None:
    server_path = Path(__file__).parent / "server.py"
    params = StdioServerParameters(command=sys.executable, args=[str(server_path)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. соединение/рукопожатие
            init = await session.initialize()
            assert init.serverInfo.name == "demo-server", "имя сервера не совпало"
            print(f"✅ соединение установлено: {init.serverInfo.name}")

            # 2. список инструментов
            result = await session.list_tools()
            names  = {t.name for t in result.tools}
            assert names == EXPECTED_TOOLS, f"ожидалось {EXPECTED_TOOLS}, получено {names}"
            print(f"✅ список инструментов корректен: {sorted(names)}")

            # 3. у каждого инструмента есть описание и схема
            for t in result.tools:
                assert t.description, f"у {t.name} нет описания"
                assert t.inputSchema, f"у {t.name} нет inputSchema"
            print("✅ у всех инструментов есть описание и input-схема")

            # 4. бонус: вызов инструмента работает
            call = await session.call_tool("add", {"a": 2, "b": 3})
            text = call.content[0].text
            assert float(text) == 5.0, f"add(2,3) вернул {text!r}"
            print(f"✅ вызов add(2, 3) = {text}")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    asyncio.run(run())
