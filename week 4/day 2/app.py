"""
Приложение: задаёт агенту вопрос, агент вызывает MCP-инструмент CRM
и использует результат в ответе.

Запуск:
    python app.py                       # демо-сценарии
    python app.py "ваш вопрос к CRM"    # свой вопрос
"""

import asyncio
import sys

from agent import MCPAgent

DEMO_QUESTIONS = [
    "Покажи всех клиентов с тарифом gold и их MRR.",
    "Какие сейчас открытые сделки и на какую сумму?",
    "Создай тикет высокого приоритета для клиента C-002 по теме «не приходят счета».",
]


async def run(questions: list[str]) -> None:
    async with MCPAgent() as agent:
        print(f"✓ Подключено к MCP. Инструменты: {', '.join(agent.tool_names)}\n")

        for q in questions:
            print("─" * 70)
            print(f"❓ {q}")
            result = await agent.ask(q)

            # показываем, какие MCP-инструменты были вызваны и что вернули
            for tc in result.tool_calls:
                short = tc.result.replace("\n", " ")
                if len(short) > 160:
                    short = short[:160] + "…"
                print(f"   🔧 MCP {tc.name}({tc.arguments}) → {short}")

            print(f"\n🤖 {result.answer}\n")


def main() -> None:
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEMO_QUESTIONS
    try:
        asyncio.run(run(questions))
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
