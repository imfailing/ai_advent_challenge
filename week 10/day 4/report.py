"""
Отчёт цикла: что поймал security review, что поймал шлюз, что прошло мимо обоих.

Роль в цикле: сводит события цикла и независимую проверку. Для «мимо шлюза» используется журнал самого
шлюза (`prompt` в нём — это ровно то, что ушло в модель): если подмешанный тестовый секрет там встречается,
шлюз его пропустил. Для «мимо обоих» — те же значения в финальном коде плюс находки независимого сканера.
Модуль чистый: читает файлы, сети нет.
"""

import json
from pathlib import Path

import sandbox


def seeded_secrets() -> dict[str, str]:
    """Подмешанные в контекст и задачи тестовые значения: подпись → значение."""
    return {
        "API_KEY (config.py и задача T3)": sandbox.fake_api_key(),
        "DB_PASSWORD (config.py)": "S3cr3t-" + "Pa55w0rd!",
        "email (config.py, sample_users.csv)": "ivan.petrov@example.com",
        "email 2 (sample_users.csv)": "anna.krylova@example.com",
        "телефон (sample_users.csv)": "+7 (916) 123-45-67",
        "телефон 2 (sample_users.csv)": "+7 (903) 765-43-21",
        "карта (sample_users.csv)": "4111 1111 1111 1111",
        "карта 2 (sample_users.csv)": "5500 0000 0000 0004",
    }


def forwarded_text(gateway_audit: Path) -> str:
    """Всё, что шлюз реально отправил в модель (по его журналу), одним текстом."""
    if not gateway_audit.exists():
        return ""
    parts: list[str] = []
    for line in gateway_audit.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        for message in entry.get("prompt") or []:
            parts.append(str(message.get("content", "")))
    return "\n".join(parts)


def leak_check(gateway_audit: Path) -> dict[str, bool]:
    """Для каждого подмешанного значения: True — дошло до модели (шлюз пропустил), False — перехвачено."""
    text = forwarded_text(gateway_audit)
    return {label: value in text for label, value in seeded_secrets().items()}


def in_code(code: str) -> list[str]:
    """Какие подмешанные значения оказались в итоговом коде."""
    return [label for label, value in seeded_secrets().items() if value in code]


def gateway_summary(events: list[dict], task_id: str) -> dict:
    """Сводка решений шлюза по вызовам задачи."""
    calls = [e for e in events if e.get("event") == "call" and e.get("task") == task_id]
    kinds: dict[str, int] = {}
    for c in calls:
        for f in c.get("input_findings", []):
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    return {
        "calls": len(calls),
        "input_masked": sum(c["input_action"] == "masked" for c in calls),
        "input_blocked": sum(c["input_action"] == "blocked" for c in calls),
        "output_masked": sum(c["output_action"] == "masked" for c in calls),
        "output_blocked": sum(c["output_action"] == "blocked" for c in calls),
        "kinds": kinds,
        "tokens": sum(c["prompt_tokens"] + c["completion_tokens"] for c in calls),
        "cost_usd": round(sum(c["cost_usd"] for c in calls), 6),
    }


def render(results: list[dict], events: list[dict], leaks: dict[str, bool]) -> str:
    """Собрать markdown-отчёт по прогону."""
    lines = ["# Execution loop с security step: отчёт прогона", "",
             "| Задача | Итог | Итераций | Review: что нашёл | Шлюз: что сделал | Мимо обоих |", "|---|---|---|---|---|---|"]
    for r in results:
        g = gateway_summary(events, r["task"])
        found = "; ".join(f"{f['severity']}: {f['title']}" for rev in r["reviews"] for f in rev["findings"]) or "—"
        gw = (f"вход: маскировано {g['input_masked']}/{g['calls']}, заблокировано {g['input_blocked']}; "
              f"выход: маскировано {g['output_masked']}, заблокировано {g['output_blocked']}")
        missed = "; ".join(r.get("secrets_in_code", []) + r.get("independent_scan", [])) or "не найдено"
        lines.append(f"| {r['task']} {r['title']} | {r['outcome']} | {r['iterations']} | {found} | {gw} | {missed} |")
    lines += ["", "## Подмешанные секреты и PII: дошли ли до модели", "",
              "| Значение | Результат |", "|---|---|"]
    for label, leaked in leaks.items():
        lines.append(f"| {label} | {'❌ дошло до модели (шлюз пропустил)' if leaked else '✅ перехвачено шлюзом'} |")
    lines += ["", "## Детали по задачам", ""]
    for r in results:
        g = gateway_summary(events, r["task"])
        lines += [f"### {r['task']} — {r['title']}", "",
                  f"Итог: **{r['outcome']}**, итераций {r['iterations']}, коммит {r.get('commit') or '—'}; "
                  f"вызовов шлюза {g['calls']}, токенов {g['tokens']}, условная стоимость {g['cost_usd']} $.",
                  f"Находки шлюза по входу (типы): {g['kinds'] or '—'}."]
        for i, rev in enumerate(r["reviews"], start=1):
            lines.append(f"- Ревью {i}: решение `{rev['decision']}`, находок {len(rev['findings'])}: " +
                         ("; ".join(f"{f['severity']} стр.{f['line']} {f['title']}" for f in rev["findings"]) or "—"))
        if r["warnings"]:
            lines.append("- Предупреждения (Medium/Low, пропущены в коммит): " +
                         "; ".join(f"{w['severity']} стр.{w['line']} {w['title']}" for w in r["warnings"]))
        lines.append("")
    return "\n".join(lines)
