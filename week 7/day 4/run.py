"""
Запуск ассистента на ЦЕЛЯХ (не «открой файл X»). Реализовано ≥2 сценария.

Для воспроизводимости: перед каждым сценарием песочница пересоздаётся
(workspace_seed.seed), снимается снимок файлов ДО, агент работает, затем
показываются вызванные инструменты и DIFF затронутых файлов.

Запуск:
    python run.py            # оба сценария
    python run.py 1          # только сценарий 1
    python run.py "<цель>"   # произвольная цель
"""

import asyncio
import difflib
import sys
from pathlib import Path

import workspace_seed
from agent import FileAgent

WORKSPACE = workspace_seed.WORKSPACE

SCENARIOS = {
    "1": ("Поиск использований компонента",
          "Найди все места в проекте, где используется компонент Logger "
          "(импорт и вызовы), и собери отчёт в файл docs/logger_usage.md: "
          "список файлов со строками использования и краткий вывод."),
    "2": ("Проверка соответствия правилу",
          "Проверь правило: каждый .py-файл должен начинаться с докстринга "
          "модуля (тройные кавычки в начале). Найди нарушителей и создай отчёт "
          "compliance_report.md со списком файлов-нарушителей и рекомендацией."),
}


def snapshot() -> dict[str, str]:
    return {str(p.relative_to(WORKSPACE)): p.read_text(encoding="utf-8", errors="ignore")
            for p in WORKSPACE.rglob("*") if p.is_file()}


def show_diffs(before: dict, after: dict) -> None:
    changed = False
    for path in sorted(set(before) | set(after)):
        b = before.get(path, "")
        a = after.get(path, "")
        if b == a:
            continue
        changed = True
        tag = "СОЗДАН" if path not in before else "ИЗМЕНЁН"
        print(f"\n  ── diff [{tag}] {path} ──")
        diff = difflib.unified_diff(b.splitlines(), a.splitlines(),
                                    fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")
        for line in list(diff)[:40]:
            print("  " + line)
    if not changed:
        print("  (файлы не изменились)")


async def run_one(agent: FileAgent, key: str, goal: str) -> None:
    workspace_seed.seed()
    before = snapshot()
    print("=" * 74)
    print(f"  ЦЕЛЬ: {goal}")
    print("=" * 74)
    run = await agent.run(goal)

    print("Действия ассистента с файлами:")
    for tc in run.tool_calls:
        arg = {k: (v[:40] + "…" if isinstance(v, str) and len(v) > 40 else v)
               for k, v in tc.args.items()}
        info = tc.result.replace("\n", " ")[:70]
        print(f"  🔧 {tc.tool}({arg}) → {info}…")

    print(f"\n🤖 {run.summary[:300]}")
    print(f"\nСозданные/изменённые файлы: {run.files_written or '—'}")
    show_diffs(before, snapshot())
    print()


async def main() -> None:
    agent = FileAgent()
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg in SCENARIOS:
        await run_one(agent, arg, SCENARIOS[arg][1])
    elif arg:
        await run_one(agent, "custom", arg)
    else:
        for key, (_, goal) in SCENARIOS.items():
            await run_one(agent, key, goal)


if __name__ == "__main__":
    asyncio.run(main())
