"""
Проверка на 2 длинных сценариях (по 10–13 сообщений):
  • ассистент на каждый (внутрибазовый) вопрос отвечает с ИСТОЧНИКАМИ;
  • ПАМЯТЬ ЗАДАЧИ накапливает цель / уточнения / ограничения;
  • ассистент НЕ теряет цель к концу длинного диалога.
"""

import uuid

import database as db
from agent import ChatAgent

# Сценарий 1 — выбор стратегии управления контекстом
SCENARIO_1 = [
    "Моя цель — выбрать стратегию управления контекстом для чат-бота. С чего начать?",
    "Какие вообще есть стратегии управления контекстом?",
    "Чем отличается Sliding Window от Sticky Facts?",
    "У меня ограничение: бюджет на токены небольшой. Это важно учесть.",
    "Какая стратегия дешевле по токенам?",
    "А что такое Branching и когда он нужен?",
    "Ещё ограничение: диалоги длинные, по 50+ сообщений.",
    "Что происходит со стоимостью при длинных диалогах в Branching?",
    "Напомни, какая у нас цель и какие ограничения мы зафиксировали?",
    "Итого: какую стратегию посоветуешь под мои ограничения?",
]

# Сценарий 2 — построение MCP-интеграции
SCENARIO_2 = [
    "Цель: построить MCP-интеграцию для агента. Объясни основы.",
    "Что такое MCP-инструмент и как он устроен?",
    "Какой транспорт использовать для локального сервера?",
    "Термин на будущее: под 'пайплайном' я имею в виду цепочку инструментов.",
    "Как сделать пайплайн из нескольких инструментов?",
    "Ограничение: инструменты должны работать по расписанию (24/7).",
    "Как реализовать периодическое выполнение инструмента?",
    "Что делает фоновый планировщик на каждом тике?",
    "Напомни мою цель и что мы уже зафиксировали.",
    "Собери итоговый план MCP-интеграции под мои требования.",
]


def run_scenario(name: str, turns: list[str], goal_keywords: list[str]) -> None:
    sid = f"test-{name}-{uuid.uuid4().hex[:6]}"
    agent = ChatAgent(session_id=sid)
    print(f"\n{'='*72}\n  СЦЕНАРИЙ: {name}  ({len(turns)} сообщений)\n{'='*72}")

    with_sources = in_domain = 0
    for i, q in enumerate(turns, 1):
        r = agent.ask(q)
        tag = "источники: " + (", ".join(sorted({s['source'] for s in r.sources}))
                               if r.sources else "—")
        print(f"\n[{i}] 👤 {q}")
        print(f"    🤖 {r.answer[:150]}{'…' if len(r.answer) > 150 else ''}")
        print(f"    📎 {tag}")
        if r.found:
            in_domain += 1
            if r.sources:
                with_sources += 1

    mem = db.get_task_memory(sid)
    print(f"\n--- ПАМЯТЬ ЗАДАЧИ в конце ---")
    print(f"  Цель:        {mem['goal']}")
    print(f"  Уточнено:    {mem['clarifications']}")
    print(f"  Ограничения: {mem['constraints']}")
    print(f"  Термины:     {mem['terms']}")

    # Проверки
    assert mem["goal"], "цель потеряна"
    # цель НЕ должна подмениться примером из документов (доставка/приложение)
    assert any(k in mem["goal"].lower() for k in goal_keywords), \
        f"цель ушла в сторону: {mem['goal']!r}"
    assert "достав" not in mem["goal"].lower(), \
        f"цель подменена примером из корпуса: {mem['goal']!r}"
    assert len(mem["constraints"]) >= 1, "ограничения не зафиксированы"
    assert with_sources == in_domain and in_domain >= 6, \
        f"не все внутрибазовые ответы с источниками: {with_sources}/{in_domain}"
    print(f"\n✅ {name}: цель сохранена «{mem['goal']}», "
          f"ограничений {len(mem['constraints'])}, "
          f"ответов с источниками {with_sources}/{in_domain}")


def main() -> None:
    db.init_db()
    run_scenario("context-strategy", SCENARIO_1, ["стратег", "контекст"])
    run_scenario("mcp-integration", SCENARIO_2, ["mcp", "интеграц"])
    print("\n✅ ОБА СЦЕНАРИЯ ПРОЙДЕНЫ")


if __name__ == "__main__":
    main()
