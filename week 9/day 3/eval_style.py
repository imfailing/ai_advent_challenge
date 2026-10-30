"""
Стиль и тон (пиратский): 20 новых запросов (не из обучения дня 6), 10 из них фактические с проверяемым
ответом. Режимы: base (без инструкций), base_prompt (проработанный стилевой промпт), tuned (адаптер дня 6).
Метрики: доля ответов «в стиле» (≥3 пиратских маркеров), среднее число маркеров, доля верных
фактических ответов (стиль не должен ломать содержание), средняя длина. → out/style_<режим>.json
Запуск: python eval_style.py <режим> [путь_к_адаптеру]
"""

import json
import re
import sys
from pathlib import Path

from common import chat, load_model

ROOT = Path(__file__).parent
STYLE_MIN_MARKERS = 3
MARKERS = re.compile(
    r"\b(ahoy|matey|mateys|arr+|aye|ye|yer|me hearties|shiver me timbers|scurvy|doubloons?|"
    r"landlubbers?|grog|jolly roger|cap'n|avast|plunder|buccaneer)\b", re.IGNORECASE)
SYSTEM_PROMPT = (
    "You are a salty old pirate. ALWAYS answer in pirate speak: open with 'Ahoy' or 'Arr', address the "
    "user as 'matey', use words like ye, yer, aye, scurvy, doubloons, shiver me timbers, and nautical "
    "metaphors. Keep the facts correct. Keep answers short (2-4 sentences)."
)
PROMPTS: list[tuple[str, list[str] | None]] = [
    ("What is the capital of Italy?", ["rome"]),
    ("How many days are in a leap year?", ["366"]),
    ("Who discovered penicillin?", ["fleming"]),
    ("What is the largest planet in the Solar System?", ["jupiter"]),
    ("What is the chemical formula of water?", ["h2o"]),
    ("Which continent is Egypt in?", ["africa"]),
    ("What is 8 times 7?", ["56"]),
    ("Who wrote 'Pride and Prejudice'?", ["austen"]),
    ("What is the freezing point of water in Celsius?", ["0", "zero"]),
    ("Which element has the atomic number 1?", ["hydrogen"]),
    ("Give me three tips for saving money.", None),
    ("How do I make a good cup of tea?", None),
    ("Describe a rainy day in a few sentences.", None),
    ("Why is sleep important?", None),
    ("Write a short welcome message for a new team member.", None),
    ("What should I consider when buying a laptop?", None),
    ("Explain what a database index is.", None),
    ("Suggest a name for a pet goldfish.", None),
    ("How can I stay focused while studying?", None),
    ("What is a good way to start learning to cook?", None),
]


def main(mode: str, adapter: str | None) -> None:
    model, tok = load_model(adapter if mode == "tuned" else None)
    rows = []
    for prompt, keys in PROMPTS:
        messages = [{"role": "user", "content": prompt}]
        if mode == "base_prompt":
            messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        reply = chat(model, tok, messages, max_new_tokens=160)
        n = len(MARKERS.findall(reply))
        rows.append({
            "prompt": prompt, "reply": reply, "markers": n, "in_style": n >= STYLE_MIN_MARKERS,
            "fact_ok": None if keys is None else any(k in reply.lower() for k in keys),
        })
    facts = [r for r in rows if r["fact_ok"] is not None]
    result = {
        "mode": mode, "n": len(rows),
        "in_style_rate": round(sum(r["in_style"] for r in rows) / len(rows), 3),
        "markers_avg": round(sum(r["markers"] for r in rows) / len(rows), 2),
        "fact_accuracy": round(sum(r["fact_ok"] for r in facts) / len(facts), 3),
        "avg_reply_chars": round(sum(len(r["reply"]) for r in rows) / len(rows)),
        "rows": rows,
    }
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"style_{mode}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
