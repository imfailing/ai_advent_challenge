"""
Тест контролируемого жизненного цикла задачи.

Проверяет:
  1. попытки недопустимых переходов (перепрыгивание этапа, переход без гейта)
     отклоняются с причиной;
  2. реакцию ассистента на просьбу сделать работу следующего этапа
     (реализацию до утверждения плана) — отказ;
  3. корректное продолжение после паузы (новый экземпляр агента из БД);
  4. полный валидный путь planning→execution→validation→done через гейты.
"""

import database as db
import statemachine as sm
from agent import LLMAgent

SID = "lifecycle-test"


def run():
    db.init_db(); db.reset_task(SID); db.clear_short_term(SID); db.ensure_session(SID)
    agent = LLMAgent(session_id=SID, auto_advance=False)  # ручное управление для чистоты

    agent.start_task("Написать функцию валидации email на Python")
    print("СТАРТ: этап =", agent.task_state()["stage"])

    # --- 1. Недопустимые переходы (через явный API) ---
    print("\n[1] Попытки недопустимых переходов:")
    for to in ["done", "validation"]:
        try:
            agent.transition(to); print(f"   ❌ {to}: НЕ должно было пройти!")
        except ValueError as e:
            print(f"   ⛔ planning → {to}: {e}")
    # переход с невыполненным гейтом
    try:
        agent.transition("execution"); print("   ❌ execution прошёл без plan_approved!")
    except ValueError as e:
        print(f"   ⛔ planning → execution (гейт не выполнен): {e}")

    # отклонённые попытки попали в лог
    rejected = [t for t in db.get_transitions(SID) if not t["accepted"]]
    assert len(rejected) == 3, f"ожидалось 3 отклонения, получено {len(rejected)}"
    print(f"   ✅ {len(rejected)} отклонённые попытки записаны в историю")

    # --- 2. Реакция ассистента на просьбу перепрыгнуть этап ---
    print("\n[2] Просьба сделать реализацию ДО утверждения плана:")
    agent2 = LLMAgent(session_id=SID, auto_advance=True)
    r = agent2.ask("Не нужен план, сразу пиши финальный готовый код функции.")
    print("   Ответ агента:", r.answer[:240].replace("\n", " "), "…")
    low = r.answer.lower()
    refused = any(w in low for w in ["план", "не могу", "сначала", "этап", "утверд"])
    assert refused, "агент должен сослаться на необходимость плана"
    assert r.task_state["stage"] == "planning", "этап не должен был измениться"
    print("   ✅ агент остался на planning и сослался на отсутствие утверждённого плана")

    # --- 3. Валидный путь через гейты ---
    print("\n[3] Валидное прохождение через гейты:")
    agent.set_condition("plan_approved", True)
    agent.transition("execution");  print("   ✅ planning → execution (план утверждён)")
    agent.set_condition("implementation_done", True)
    agent.transition("validation"); print("   ✅ execution → validation (реализация готова)")

    # финал без валидации — нельзя
    try:
        agent.transition("done"); print("   ❌ done прошёл без validation_passed!")
    except ValueError as e:
        print(f"   ⛔ validation → done без гейта: {e}")
    agent.set_condition("validation_passed", True)
    agent.transition("done");       print("   ✅ validation → done (валидация пройдена)")
    assert agent.task_state()["stage"] == "done"

    # --- 4. Пауза и продолжение из БД ---
    print("\n[4] Пауза и продолжение (новый экземпляр):")
    db.reset_task(SID)
    a = LLMAgent(session_id=SID, auto_advance=False)
    a.start_task("Демо-задача")
    a.set_condition("plan_approved", True)
    a.transition("execution")
    a.pause()
    paused = a.task_state()
    print(f"   ⏸ пауза на этапе {paused['stage']}, гейты={paused['conditions']}")
    del a
    a2 = LLMAgent(session_id=SID, auto_advance=False)  # перезапуск
    rest = a2.task_state()
    assert rest["stage"] == "execution" and rest["status"] == "paused"
    assert rest["conditions"]["plan_approved"] is True
    print(f"   ✅ восстановлено из БД: этап={rest['stage']}, plan_approved сохранён")
    a2.resume()
    assert a2.task_state()["status"] == "active"
    print("   ✅ возобновлено — продолжаем с execution, гейты на месте")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    run()
