"""
Прогон ученика (Qwen2.5-1.5B-Instruct, с адаптером или без) по тесту дня 9 с замером задержки каждого
запроса (batch=1, жадно, один прогрев в начале). Сохраняет ответ, число токенов и секунды.
Запуск: [MERGE=1] python eval_student.py <имя> [путь_к_адаптеру] → out/student_<имя>.json
MERGE=1 — слить адаптер с весами перед замером (без накладных расходов LoRA на каждом шаге).
"""

import json
import os
import sys
from pathlib import Path

import schema
from common import load_model, timed_chat

ROOT = Path(__file__).parent


def main(name: str, adapter: str | None) -> None:
    rows = [json.loads(line) for line in (ROOT / "data" / "test_final.jsonl").read_text("utf-8").splitlines()]
    model, tok = load_model(adapter)
    if adapter and os.environ.get("MERGE"):
        model = model.merge_and_unload()
    msgs = lambda text: [{"role": "system", "content": schema.SYSTEM_PROMPT}, {"role": "user", "content": text}]  # noqa: E731
    timed_chat(model, tok, msgs(rows[0]["text"]), max_new_tokens=16)  # прогрев
    out = []
    for r in rows:
        res = timed_chat(model, tok, msgs(r["text"]), max_new_tokens=200)
        out.append({"id": r["id"], **res})
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"student_{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(name, "средняя задержка, с:", round(sum(o["seconds"] for o in out) / len(out), 2))  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
