"""
Ответы учителя (DeepSeek) на письма: промпт schema.SYSTEM_PROMPT, temperature 0, JSON-режим. Пишет
ответ, токены и задержку каждого запроса. Запуск: python label_teacher.py <test|pool> → out/teacher_<имя>.json
"""

import json
import sys
from pathlib import Path

import schema
import teacher

ROOT = Path(__file__).parent


def main(name: str) -> None:
    rows = [json.loads(line) for line in (ROOT / "data" / f"{name}.jsonl").read_text("utf-8").splitlines()]
    jobs = [[{"role": "system", "content": schema.SYSTEM_PROMPT}, {"role": "user", "content": r["text"]}] for r in rows]
    results = teacher.call_many(jobs, temperature=0.0, max_tokens=300, json_mode=True)
    out = [{"id": r["id"], "reply": res.get("content"), "error": res.get("error"),
            "prompt_tokens": res.get("prompt_tokens"), "completion_tokens": res.get("completion_tokens"),
            "seconds": res.get("seconds")} for r, res in zip(rows, results, strict=True)]
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"teacher_{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(name, "ответов:", sum(o["reply"] is not None for o in out), "из", len(out))  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1])
