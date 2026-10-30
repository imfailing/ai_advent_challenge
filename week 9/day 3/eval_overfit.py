"""
Проверка чекпоинтов переобучения на задаче дня 7 (коммит → {"type": ...}): для каждого чекпоинта —
accuracy и строгий формат на eval дня 7 (104 коммита) и на «непохожих» входах (data/unlike.jsonl:
8 русскоязычных коммитов и 12 обычных вопросов). Для русских коммитов считаем accuracy, для обычных
вопросов — долю ответов, где формат `{"type": ...}` «протёк».
Запуск: python eval_overfit.py <имя> <путь_к_адаптеру|none> → out/overfit_<имя>.json
"""

import json
import re
import sys
from pathlib import Path

from common import chat, load_model

ROOT = Path(__file__).parent
EVAL_PATH = ROOT / ".." / "day 2" / "data" / "eval.jsonl"
TYPES = ["feat", "fix", "docs", "refactor", "test", "chore", "perf", "ci"]


def parse_type(text: str) -> tuple[str | None, bool]:
    """Тип из ответа и признак строгого формата (весь ответ — один JSON с ключом type)."""
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict) and list(obj) == ["type"] and obj["type"] in TYPES:
            return obj["type"], True
    except json.JSONDecodeError:
        pass
    m = re.search(r'"type"\s*:\s*"([a-z]+)"', text)
    return (m.group(1) if m and m.group(1) in TYPES else None), False


def main(name: str, adapter: str | None) -> None:
    model, tok = load_model(adapter)
    eval_rows = [json.loads(line) for line in EVAL_PATH.read_text("utf-8").splitlines()]
    unlike = [json.loads(line) for line in (ROOT / "data" / "unlike.jsonl").read_text("utf-8").splitlines()]
    hits = strict = 0
    for ex in eval_rows:
        reply = chat(model, tok, [ex["messages"][0]], max_new_tokens=40)
        pred, ok = parse_type(reply)
        hits += pred == ex["type"]
        strict += ok
    rows = []
    for ex in unlike:
        reply = chat(model, tok, [{"role": "user", "content": ex["prompt"]}], max_new_tokens=80)
        pred, _ = parse_type(reply)
        rows.append({"kind": ex["kind"], "prompt": ex["prompt"], "reply": reply,
                     "leaked": '{"type"' in reply, "correct": pred == ex.get("gold")})
    ru = [r for r in rows if r["kind"] == "ru_commit"]
    non = [r for r in rows if r["kind"] == "non_commit"]
    result = {
        "name": name, "adapter": adapter,
        "eval_accuracy": round(hits / len(eval_rows), 3),
        "eval_strict_format": round(strict / len(eval_rows), 3),
        "ru_commit_accuracy": round(sum(r["correct"] for r in ru) / len(ru), 3),
        "non_commit_type_leak": round(sum(r["leaked"] for r in non) / len(non), 3),
        "unlike_rows": rows,
    }
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"overfit_{name}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "unlike_rows"}))  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1], None if sys.argv[2] == "none" else sys.argv[2])
