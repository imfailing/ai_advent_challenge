"""
Проверка файлового ассистента:
  • по ЦЕЛИ агент сам читает/ищет по нескольким файлам (не «открой X»);
  • создаёт файл-результат (сохраняется в песочнице);
  • анализ корректен (сценарий проверки правила находит реальных нарушителей);
  • результат воспроизводим (песочница пересоздаётся перед запуском).

Нужен DEEPSEEK_API_KEY.
"""

import asyncio

import workspace_seed
from agent import FileAgent

WS = workspace_seed.WORKSPACE


async def main() -> None:
    agent = FileAgent()

    # Сценарий 1 — поиск использований компонента
    workspace_seed.seed()
    run = await agent.run(
        "Найди все места использования компонента Logger и собери отчёт в файл "
        "docs/logger_usage.md со списком файлов и строк.")
    tools = [tc.tool for tc in run.tool_calls]
    assert tools.count("read_file") + tools.count("search") >= 2, \
        f"агент не искал/читал по файлам: {tools}"
    assert "write_file" in tools, "агент ничего не создал"
    report = WS / "docs" / "logger_usage.md"
    assert report.exists(), "отчёт не сохранён в песочнице"
    text = report.read_text(encoding="utf-8")
    assert "service_a.py" in text and "service_b.py" in text, "в отчёте нет мест использования"
    files_read = {tc.args.get("path") for tc in run.tool_calls if tc.tool == "read_file"}
    print(f"✅ сценарий 1: агент прочитал {len(files_read)} файлов, создал {report.relative_to(WS)}")

    # Сценарий 2 — проверка правила (докстринг модуля)
    workspace_seed.seed()
    run = await agent.run(
        "Проверь, что каждый .py начинается с докстринга модуля; создай отчёт "
        "compliance_report.md со списком нарушителей.")
    assert "write_file" in [tc.tool for tc in run.tool_calls]
    rep = WS / "compliance_report.md"
    assert rep.exists(), "отчёт о соответствии не создан"
    low = rep.read_text(encoding="utf-8").lower()
    # реальные нарушители — config.py и utils.py (без докстринга модуля)
    assert "config.py" in low and "utils.py" in low, "не найдены реальные нарушители"
    print(f"✅ сценарий 2: агент проверил файлы, нашёл нарушителей (config.py, utils.py), "
          f"создал {rep.relative_to(WS)}")

    # Воспроизводимость: seed возвращает исходное состояние
    workspace_seed.seed()
    assert not (WS / "docs").exists() and not rep.exists(), "seed не сбросил результаты"
    print("✅ воспроизводимость: seed пересоздаёт песочницу в исходное состояние")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — ассистент выполняет реальные операции с файлами")


if __name__ == "__main__":
    asyncio.run(main())
