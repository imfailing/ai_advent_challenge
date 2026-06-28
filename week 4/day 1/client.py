"""
Минимальный MCP-клиент.

Что делает:
  1. устанавливает MCP-соединение с сервером по stdio
     (запускает server.py как подпроцесс);
  2. выполняет initialize-рукопожатие;
  3. получает список доступных инструментов через list_tools()
     и выводит их (имя, описание, входная схема).

Запуск:
    python client.py
    python client.py -- python путь/к/другому_server.py   # подключиться к иному серверу
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_params() -> StdioServerParameters:
    """
    Параметры запуска MCP-сервера.
    По умолчанию — локальный server.py через тот же интерпретатор Python.
    Можно переопределить командой после '--':
        python client.py -- npx -y @modelcontextprotocol/server-everything
    """
    if "--" in sys.argv:
        idx  = sys.argv.index("--")
        cmd  = sys.argv[idx + 1:]
        if not cmd:
            raise SystemExit("После '--' укажите команду запуска сервера")
        return StdioServerParameters(command=cmd[0], args=cmd[1:])

    server_path = Path(__file__).parent / "server.py"
    return StdioServerParameters(command=sys.executable, args=[str(server_path)])


async def list_mcp_tools() -> list:
    params = _server_params()
    print(f"→ Запускаю MCP-сервер: {params.command} {' '.join(params.args)}")

    # 1. Устанавливаем соединение по stdio
    async with stdio_client(params) as (read, write):
        # 2. Открываем сессию и выполняем рукопожатие
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            srv = init_result.serverInfo
            print(f"✓ Соединение установлено. Сервер: "
                  f"{srv.name} v{srv.version}")
            print(f"  Протокол MCP: {init_result.protocolVersion}\n")

            # 3. Запрашиваем список инструментов
            result = await session.list_tools()
            tools  = result.tools

            print(f"✓ Получено инструментов: {len(tools)}\n")
            for i, tool in enumerate(tools, 1):
                print(f"{i}. {tool.name}")
                if tool.description:
                    print(f"   описание: {tool.description}")
                props = (tool.inputSchema or {}).get("properties", {})
                if props:
                    args = ", ".join(
                        f"{n}: {p.get('type', '?')}" for n, p in props.items())
                    print(f"   параметры: {args}")
                print()

            return tools


def main() -> None:
    try:
        tools = asyncio.run(list_mcp_tools())
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    if not tools:
        print("⚠ Сервер не вернул ни одного инструмента", file=sys.stderr)
        sys.exit(2)
    print("Готово ✓")


if __name__ == "__main__":
    main()
