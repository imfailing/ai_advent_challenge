"""
Проверка «добавляет ли тюн знания»: 40 выдуманных фактов, три набора вопросов — формулировки из
обучения (train), перефразировки (paraphrase) и обратные вопросы (reverse). Режимы: base, base_facts
(факты в системном промпте), tuned (адаптер знаний), tuned_facts (адаптер + факты в промпте).
Верно = ожидаемый ответ (нормализованный) содержится в ответе модели. Результат — out/knowledge_<режим>.json.
Запуск: python eval_knowledge.py <режим> [путь_к_адаптеру]
"""

import json
import sys
from pathlib import Path

from common import chat, load_model
from scoring import is_correct

ROOT = Path(__file__).parent
FACTS_HEADER = "Answer the question using ONLY these facts. Reply in one short sentence.\nFacts:\n"


def main(mode: str, adapter: str | None) -> None:
    facts = json.loads((ROOT / "data" / "facts.json").read_text("utf-8"))
    facts_text = (ROOT / "data" / "facts_prompt.txt").read_text("utf-8")
    model, tok = load_model(adapter if mode.startswith("tuned") else None)
    sets = {
        "train": [(q, f["answer"], f["kind"]) for f in facts for q in f["train_questions"]],
        "paraphrase": [(q, f["answer"], f["kind"]) for f in facts for q in f["test_questions"]],
        "reverse": [(f["reverse_question"], f["reverse_answer"], f["kind"]) for f in facts],
    }
    result: dict = {"mode": mode, "adapter": adapter, "sets": {}}
    for name, items in sets.items():
        rows = []
        for question, answer, kind in items:
            messages = [{"role": "user", "content": question}]
            if mode.endswith("facts"):
                messages.insert(0, {"role": "system", "content": FACTS_HEADER + facts_text})
            reply = chat(model, tok, messages, max_new_tokens=48)
            rows.append({"question": question, "answer": answer, "kind": kind, "reply": reply,
                         "correct": is_correct(reply, answer)})
        by_kind = {k: round(sum(r["correct"] for r in rows if r["kind"] == k)
                            / sum(1 for r in rows if r["kind"] == k), 3)
                   for k in sorted({r["kind"] for r in rows})}
        result["sets"][name] = {
            "n": len(rows), "accuracy": round(sum(r["correct"] for r in rows) / len(rows), 3),
            "by_kind": by_kind, "rows": rows,
        }
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"knowledge_{mode}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(mode, {k: v["accuracy"] for k, v in result["sets"].items()})  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
