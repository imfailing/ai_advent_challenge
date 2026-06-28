"""
Приложение: подключается к MCP-серверу с фоновым планировщиком,
даёт ему поработать и просит агента выдать сводку.

Демонстрирует «агента 24/7»: пока приложение работает, планировщик собирает
данные, а агент по запросу возвращает агрегированный результат.

Запуск:
    python app.py                  # демо: подождать сбор → попросить сводку
    python app.py "ваш вопрос"     # свой вопрос к мониторинг-агенту
"""

import asyncio
import sys

from agent import MCPAgent

DEMO = [
    "Поставь напоминание «снять метрики» через 2 секунды.",
    "Дай сводку по метрике за последние 5 минут: среднее, минимум, максимум.",
    "Какой статус планировщика и сколько уже собрано измерений?",
]


async def run(questions: list[str], warmup: float) -> None:
    async with MCPAgent() as agent:
        print(f"✓ Подключено к MCP. Инструменты: {', '.join(agent.tool_names)}")
        print(f"⏳ Планировщик собирает данные {warmup:.0f}с…\n")
        await asyncio.sleep(warmup)   # даём планировщику накопить измерения

        for q in questions:
            print("─" * 70)
            print(f"❓ {q}")
            result = await agent.ask(q)
            for tc in result.tool_calls:
                short = tc.result.replace("\n", " ")
                if len(short) > 150:
                    short = short[:150] + "…"
                print(f"   🔧 MCP {tc.name}({tc.arguments}) → {short}")
            print(f"\n🤖 {result.answer}\n")


def main() -> None:
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEMO
    try:
        asyncio.run(run(questions, warmup=5.0))
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
