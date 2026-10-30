"""
Прогон 40 задач вне домена (ood_tasks.py) на базовой модели или с адаптером; считает accuracy по
категориям и «следы» тюна в ответах: доля ответов с `{"type"`, среднее число пиратских маркеров,
средняя длина ответа. Запуск: python eval_ood.py <имя> [путь_к_адаптеру] → out/ood_<имя>.json
"""

import json
import re
import sys
from pathlib import Path

from common import chat, load_model
from ood_tasks import TASKS
from scoring import check

ROOT = Path(__file__).parent
PIRATE_RE = re.compile(
    r"\b(ahoy|matey|mateys|arr+|aye|ye|yer|me hearties|shiver me timbers|scurvy|doubloons?|"
    r"landlubbers?|grog|jolly roger|cap'n|avast)\b", re.IGNORECASE)


def main(name: str, adapter: str | None) -> None:
    model, tok = load_model(adapter)
    rows = []
    for task in TASKS:
        reply = chat(model, tok, [{"role": "user", "content": task["prompt"]}], max_new_tokens=200)
        kind, arg = task["check"]
        rows.append({"cat": task["cat"], "prompt": task["prompt"], "reply": reply,
                     "ok": check(kind, arg, reply)})
    cats = sorted({r["cat"] for r in rows})
    result = {
        "name": name, "adapter": adapter, "n": len(rows),
        "accuracy": round(sum(r["ok"] for r in rows) / len(rows), 3),
        "by_cat": {c: round(sum(r["ok"] for r in rows if r["cat"] == c)
                            / sum(1 for r in rows if r["cat"] == c), 3) for c in cats},
        "type_json_leak": round(sum('{"type"' in r["reply"] for r in rows) / len(rows), 3),
        "pirate_markers_avg": round(sum(len(PIRATE_RE.findall(r["reply"])) for r in rows) / len(rows), 2),
        "avg_reply_chars": round(sum(len(r["reply"]) for r in rows) / len(rows)),
        "rows": rows,
    }
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"ood_{name}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False))  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
