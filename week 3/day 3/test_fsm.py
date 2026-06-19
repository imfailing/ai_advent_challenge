"""
Тест формализованного состояния задачи: продвижение по этапам,
ПАУЗА на этапе и ПРОДОЛЖЕНИЕ без повторных объяснений.

Ключевая проверка: после паузы создаётся НОВЫЙ экземпляр агента
(симуляция перезапуска процесса). Он не помнит ничего в RAM, но
восстанавливает этап/шаг/ожидаемое действие из БД и продолжает работу.
"""

import database as db
import statemachine as sm
from agent import LLMAgent

SID = "fsm-test"


def show(state, title):
    print(f"\n[{title}] этап={state['stage']} · статус={state['status']}")
    print(f"   шаг: {state['current_step']}")
    print(f"   ожидается: {state['expected_action']}")


def run():
    db.init_db()
    db.reset_task(SID)
    db.clear_short_term(SID)
    db.ensure_session(SID)

    agent = LLMAgent(session_id=SID, auto_advance=True)

    # 1. Старт задачи
    st = agent.start_task("Написать функцию валидации email на Python")
    show(st, "СТАРТ")
    assert st["stage"] == "planning"

    # 2. Планирование
    r = agent.ask("Какой план? Опиши шаги решения.")
    show(r.task_state, f"После хода 1 (ответ: {r.answer[:60]}…)")

    # 3. Двигаемся к выполнению
    r = agent.ask("План хороший, утверждаю. Приступай к реализации.")
    show(r.task_state, "После утверждения плана")

    # 4. ПАУЗА на текущем этапе
    paused = agent.pause()
    show(paused, "⏸ ПАУЗА")
    assert paused["status"] == "paused"
    stage_at_pause = paused["stage"]
    step_at_pause  = paused["current_step"]

    # 5. Во время паузы продвижение запрещено
    r = agent.ask("(во время паузы) можешь продолжить?")
    assert r.task_state["stage"] == stage_at_pause, "этап не должен меняться на паузе"
    assert r.task_state["status"] == "paused"
    print("\n✅ На паузе этап заморожен — продвижения нет")

    # 6. СИМУЛЯЦИЯ ПЕРЕЗАПУСКА: новый агент, пустой RAM
    del agent
    print("\n--- симуляция перезапуска процесса (новый экземпляр агента) ---")
    agent2 = LLMAgent(session_id=SID, auto_advance=True)
    restored = agent2.task_state()
    show(restored, "ВОССТАНОВЛЕНО ИЗ БД")
    assert restored["stage"] == stage_at_pause
    assert restored["current_step"] == step_at_pause
    print("✅ Состояние полностью восстановлено из БД")

    # 7. Возобновление и продолжение БЕЗ повторных объяснений
    agent2.resume()
    r = agent2.ask("Продолжаем.")
    print(f"\n[ПРОДОЛЖЕНИЕ после паузы]")
    print(f"Ответ агента: {r.answer[:300]}")
    show(r.task_state, "После возобновления")

    # Агент НЕ должен переспрашивать, что за задача
    low = r.answer.lower()
    asks_again = any(p in low for p in
                     ["какая задача", "что нужно сделать", "напомни задачу",
                      "уточните задачу", "с чего начать"])
    assert not asks_again, "агент переспросил задачу — провал"
    print("\n✅ Агент продолжил с текущего шага, не переспрашивая задачу")

    # 8. Лог переходов
    print("\n--- История переходов ---")
    for t in db.get_transitions(SID):
        frm = t["from_stage"] or "—"
        print(f"   {frm} → {t['to_stage']}  ({t['note']})")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    run()
