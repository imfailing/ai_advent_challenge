"""
Сравнение трёх вариантов на тесте дня 9: ученик до обучения, ученик после, учитель. Считает долю
валидного JSON, точность по полям и полное совпадение с эталоном, согласие с учителем, разбивку по
категориям, задержку и стоимость запроса. Читает out/teacher_test.json, out/student_<имя>.json.
Результат — out/compare.json и таблица в stdout. Запуск: python compare.py
"""

import json
import statistics
from pathlib import Path

import schema

ROOT = Path(__file__).parent
# Допущения стоимости (не измерены, см. REPORT.md): цены DeepSeek за 1 млн токенов, USD; сервер — мощность и тариф.
TEACHER_PRICE_IN, TEACHER_PRICE_OUT = 0.14, 0.28
SERVER_WATTS, KWH_PRICE = 100, 0.10
MODELS = ["student_base", "student_tuned", "student_tuned_merged", "teacher"]


def load_replies(name: str) -> dict[int, dict]:
    """Ответы модели по id письма: {reply, seconds, prompt_tokens, new_tokens}."""
    if name == "teacher":
        raw = json.loads((ROOT / "out" / "teacher_test.json").read_text("utf-8"))
        return {o["id"]: {"reply": o["reply"] or "", "seconds": o["seconds"], "prompt_tokens": o["prompt_tokens"],
                          "new_tokens": o["completion_tokens"]} for o in raw}
    raw = json.loads((ROOT / "out" / f"{name}.json").read_text("utf-8"))
    return {o["id"]: o for o in raw}


def request_cost(name: str, r: dict) -> float:
    """Стоимость одного запроса, USD: токены × тариф (учитель) или энергия сервера (ученик)."""
    if name == "teacher":
        return (r["prompt_tokens"] * TEACHER_PRICE_IN + r["new_tokens"] * TEACHER_PRICE_OUT) / 1e6
    return SERVER_WATTS / 1000 * r["seconds"] / 3600 * KWH_PRICE


def evaluate(name: str, rows: list[dict], teacher_preds: dict[int, dict | None]) -> dict:
    """Метрики одной модели на тесте."""
    replies = load_replies(name)
    hits = {k: 0 for k in schema.FIELDS}
    agree = {k: 0 for k in schema.FIELDS}
    by_cat: dict[str, list[bool]] = {}
    valid = full = summary_ok = 0
    for row in rows:
        pred = schema.parse_reply(replies[row["id"]]["reply"])
        errors = schema.schema_errors(pred)
        valid += not errors
        summary_ok += "summary" not in errors and pred is not None
        h = schema.field_hits(pred, row["gold"])
        for k, v in h.items():
            hits[k] += v
        ok = all(h.values())
        full += ok
        by_cat.setdefault(row["gold"]["category"], []).append(ok)
        t = teacher_preds[row["id"]]
        for k in schema.FIELDS:
            agree[k] += pred is not None and t is not None and pred.get(k) == t.get(k)
    n = len(rows)
    secs = [replies[r["id"]]["seconds"] for r in rows]
    return {
        "n": n, "valid_json": round(valid / n, 3), "summary_ok": round(summary_ok / n, 3),
        "full_match": round(full / n, 3), "fields": {k: round(v / n, 3) for k, v in hits.items()},
        "agree_with_teacher": {k: round(v / n, 3) for k, v in agree.items()},
        "by_category_full": {c: round(sum(v) / len(v), 3) for c, v in sorted(by_cat.items())},
        "latency_mean_s": round(statistics.mean(secs), 2), "latency_p50_s": round(statistics.median(secs), 2),
        "latency_p95_s": round(sorted(secs)[int(0.95 * (n - 1))], 2),
        "avg_new_tokens": round(statistics.mean(replies[r["id"]]["new_tokens"] for r in rows)),
        "cost_per_request_usd": round(statistics.mean(request_cost(name, replies[r["id"]]) for r in rows), 7),
    }


def main() -> None:
    rows = [json.loads(line) for line in (ROOT / "data" / "test_final.jsonl").read_text("utf-8").splitlines()]
    t_replies = load_replies("teacher")
    teacher_preds = {r["id"]: schema.parse_reply(t_replies[r["id"]]["reply"]) for r in rows}
    result = {name: evaluate(name, rows, teacher_preds) for name in MODELS if (
        name == "teacher" or (ROOT / "out" / f"{name}.json").exists())}
    (ROOT / "out" / "compare.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    cols = list(result)
    print("метрика".ljust(26), *[c.rjust(14) for c in cols])  # noqa: T201
    for key in ("valid_json", "summary_ok", "full_match", "latency_mean_s", "latency_p95_s", "avg_new_tokens",
                "cost_per_request_usd"):
        print(key.ljust(26), *[str(result[c][key]).rjust(14) for c in cols])  # noqa: T201
    for k in schema.FIELDS:
        print(f"поле {k}".ljust(26), *[str(result[c]["fields"][k]).rjust(14) for c in cols])  # noqa: T201


if __name__ == "__main__":
    main()
