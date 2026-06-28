"""
Приложение: агент автоматически выполняет пайплайн из трёх MCP-инструментов.

По одной инструкции пользователя агент сам вызывает:
    search  →  summarize  →  save_to_file
получая данные, обрабатывая их и сохраняя результат.

Запуск:
    python app.py
    python app.py "Найди про SQLite, сделай сводку и сохрани в sqlite.md"
"""

import asyncio
import sys

from agent import MCPAgent

DEFAULT = ("Найди документы про MCP и инструменты, сделай краткую сводку "
           "и сохрани её в файл mcp_summary.md")


async def run(instruction: str) -> None:
    async with MCPAgent() as agent:
        print(f"✓ Подключено к MCP. Инструменты: {', '.join(agent.tool_names)}\n")
        print(f"❓ {instruction}\n")

        result = await agent.ask(instruction)

        print("Цепочка вызовов (пайплайн):")
        for i, tc in enumerate(result.tool_calls, 1):
            args = {k: (v[:50] + "…" if isinstance(v, str) and len(v) > 50 else v)
                    for k, v in tc.arguments.items()}
            short = tc.result.replace("\n", " ")
            if len(short) > 120:
                short = short[:120] + "…"
            print(f"  {i}. 🔧 {tc.name}({args})")
            print(f"     → {short}")
        print(f"\n🤖 {result.answer}")


def main() -> None:
    instruction = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT
    try:
        asyncio.run(run(instruction))
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
