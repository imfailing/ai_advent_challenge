"""Проверка стенда prompt injection (без сети: модель подменяется через mock.patch)."""
from unittest import mock

import injection_lab as lab


def main() -> None:
    leak = lab.ATTACKS[4]
    assert lab.is_success(leak, f"Вот код: {lab.CANARY}")
    assert not lab.is_success(leak, "Не могу поделиться внутренними настройками.")
    print("✅ is_success: утечка канарейки определяется, отказ — нет")

    with mock.patch("injection_lab.chat", return_value="Я отвечаю только про кредиты."):
        res = lab.run_suite(lab.STRONG_PROMPT)
    assert len(res) == len(lab.ATTACKS) and not any(r["success"] for r in res)
    print("✅ run_suite: отказ на все атаки = 0 сработавших")

    with mock.patch("injection_lab.chat", return_value=f"DAN-РЕЖИМ ВКЛЮЧЁН {lab.CANARY} свёкла Йо-хо-хо def f(x):"):
        res = lab.run_suite(lab.WEAK_PROMPT)
    assert all(r["success"] for r in res)
    report = lab.render_report("t", lab.WEAK_PROMPT, res)
    assert "СРАБОТАЛА" in report and lab.CANARY in report
    print("✅ render_report: отчёт содержит вердикты")

    with mock.patch("injection_lab.chat", return_value="Не могу.") as m:
        res = lab.run_suite(lab.WEAK_PROMPT, lab.HARD_ATTACKS)
    assert len(res) == len(lab.HARD_ATTACKS) and not any(r["success"] for r in res)
    multi = next(a for a in lab.HARD_ATTACKS if a.history)
    assert any(c.args[2] == multi.history for c in m.call_args_list)
    print("✅ HARD_ATTACKS: история многоходовой атаки передаётся в chat")

    mixed = next(a for a in lab.HARD_ATTACKS if a.name == "mixed-task")
    assert not lab.is_success(mixed, "Рецепт блинов я не могу предоставить, отвечаю только про кредиты.")
    assert lab.is_success(mixed, "Ингредиенты: 200 г муки, яйца, молоко.")
    print("✅ mixed-task: отказ со словом «блины» не считается успехом атаки")

    empty = [{"name": "mixed-task", "technique": "t", "attack": "a", "answer": "", "success": False, "inconclusive": True}]
    assert "неопределённо" in lab.render_report("t", "p", empty)
    with mock.patch("injection_lab.chat", return_value="Ингредиенты: яйца") as m:
        fixed = lab.retry_empty("p", empty, lab.HARD_ATTACKS)
    assert m.call_count == 1 and fixed[0]["success"] and not fixed[0]["inconclusive"]
    print("✅ retry_empty: пустой ответ перезапрашивается, вердикт пересчитан")

    assert lab.CANARY in lab.STRONG_PROMPT and lab.CANARY in lab.WEAK_PROMPT
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — стенд prompt injection (эвристики, отчёт)")


if __name__ == "__main__":
    main()
