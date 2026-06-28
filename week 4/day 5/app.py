"""
Приложение: агент работает с НЕСКОЛЬКИМИ MCP-серверами и выполняет
длинный флоу, выбирая инструменты с разных серверов.

Запуск:
    python app.py
    python app.py "ваш составной запрос"
"""

import asyncio
import sys

from agent import MultiMCPAgent, default_servers

# Длинный составной сценарий: задействует CRM + базу знаний + заметки.
SCENARIO = (
    "Подними карточку клиента C-003 и его открытые сделки. "
    "Затем найди в базе знаний информацию про лицензирование и модуль аналитики, "
    "сделай по ней краткую сводку. "
    "В конце сохрани заметку с заголовком «Бриф по C-003», где собери: клиента, "
    "его открытые сделки и сводку из базы знаний."
)


async def run(instruction: str) -> None:
    async with MultiMCPAgent(default_servers()) as agent:
        # покажем, инструменты каких серверов доступны
        servers: dict[str, list[str]] = {}
        for full in agent.tools:
            label, tool = full.split("__", 1)
            servers.setdefault(label, []).append(tool)
        print("✓ Подключены MCP-серверы:")
        for label, tools in servers.items():
            print(f"   • {label}: {', '.join(tools)}")
        print(f"\n❓ {instruction}\n")

        result = await agent.ask(instruction)

        print("Флоу вызовов (маршрутизация по серверам):")
        for i, tc in enumerate(result.tool_calls, 1):
            short = tc.result.replace("\n", " ")
            if len(short) > 110:
                short = short[:110] + "…"
            print(f"  {i}. [{tc.server}] {tc.tool}({tc.arguments})")
            print(f"     → {short}")
        print(f"\n🤖 {result.answer}")


def main() -> None:
    instruction = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else SCENARIO
    try:
        asyncio.run(run(instruction))
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
