"""
Тест работы в рамках инвариантов.

Сценарий:
  1. задаём инварианты (архитектура, стек, бизнес-правило);
  2. КОНФЛИКТНЫЙ запрос — нарушает инварианты → агент должен отказаться
     и объяснить, какой инвариант нарушается;
  3. СОВМЕСТИМЫЙ запрос — в рамках инвариантов → агент помогает.
"""

import database as db
from agent import LLMAgent

SID = "inv-test"

INVARIANTS = [
    ("architecture",  "Архитектура строго монолитная. Микросервисы запрещены."),
    ("stack",         "Бэкенд только на Python. Вводить другие языки (Go, Java, Rust) нельзя."),
    ("tech_decision", "База данных — только PostgreSQL. Другие СУБД использовать нельзя."),
    ("business_rule", "Все персональные данные хранятся только на серверах в РФ (152-ФЗ)."),
]


def run():
    db.init_db()
    db.ensure_session(SID)
    db.clear_short_term(SID)
    for inv in db.list_invariants(SID):
        db.delete_invariant(inv["id"], SID)
    for cat, content in INVARIANTS:
        db.add_invariant(SID, cat, content)

    print("ИНВАРИАНТЫ:")
    for cat, content in INVARIANTS:
        print(f"  [{db.INVARIANT_CATEGORIES[cat]}] {content}")
    print("=" * 72)

    agent = LLMAgent(session_id=SID, guard=True)

    # --- 1. КОНФЛИКТНЫЙ запрос ---
    conflict = ("Давай перепишем бэкенд на Go, разнесём его на микросервисы "
                "и переедем на MongoDB в облаке AWS (Европа). Накидай план.")
    print(f"\n🔴 КОНФЛИКТНЫЙ ЗАПРОС:\n   {conflict}")
    r = agent.ask(conflict)
    print(f"\nОТВЕТ:\n{r.answer}")
    c = r.compliance
    print(f"\nВЕРДИКТ СТРАЖА: checked={c.checked} compliant={c.compliant} refused={c.refused}")
    if c.violations:
        print("Зафиксированные нарушения:")
        for v in c.violations:
            print(f"  - {v.get('invariant','')}: {v.get('reason','')}")
    assert c.compliant, "конфликтный запрос должен закончиться соответствием (отказом)"
    print("✅ Агент не нарушил инварианты на конфликтном запросе")

    # --- 2. СОВМЕСТИМЫЙ запрос ---
    db.clear_short_term(SID)
    compatible = ("Нужно ускорить тяжёлые SQL-запросы к нашей базе. "
                  "Предложи решение в рамках наших ограничений.")
    print("\n" + "=" * 72)
    print(f"\n🟢 СОВМЕСТИМЫЙ ЗАПРОС:\n   {compatible}")
    r2 = agent.ask(compatible)
    print(f"\nОТВЕТ:\n{r2.answer[:500]}…")
    c2 = r2.compliance
    print(f"\nВЕРДИКТ СТРАЖА: checked={c2.checked} compliant={c2.compliant} refused={c2.refused}")
    assert c2.compliant, "совместимый запрос должен пройти"
    assert not c2.refused, "совместимый запрос не должен быть отказом"
    print("✅ Совместимый запрос обработан в рамках инвариантов")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    run()
