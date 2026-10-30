"""
Оценка на data/eval.jsonl в одном из режимов: base_plain (база, вход без инструкций),
base_prompt (база + проработанный промпт с правилами и примерами), tuned (LoRA-адаптер, вход как в
base_plain). Жадная генерация. Метрики: accuracy (JSON достаётся из ответа), strict_format
(весь ответ — ровно один валидный JSON {"type": ...}), macro-F1, accuracy по классам.
Запуск: python eval_model.py <режим>. Результат — out/eval_<режим>.json.
"""

import json
import re
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ROOT = Path(__file__).parent
TYPES = ["feat", "fix", "docs", "refactor", "test", "chore", "perf", "ci"]
MAX_NEW_TOKENS = 40
SYSTEM_PROMPT = """You classify git commit messages into Conventional Commit types.
Allowed types: feat, fix, docs, refactor, test, chore, perf, ci.
- feat: a new feature or capability for users.
- fix: a bug fix.
- docs: documentation-only changes.
- refactor: code restructuring with no behavior change.
- test: adding or changing tests only.
- chore: maintenance, dependency updates, releases, tooling, housekeeping.
- perf: a change that improves performance.
- ci: changes to CI/CD configuration or pipelines.
Answer with ONLY a JSON object of the form {"type": "<type>"} and nothing else.

Examples:
Commit message:
add support for custom headers in the client
-> {"type": "feat"}
Commit message:
prevent crash when the config file is empty
-> {"type": "fix"}
Commit message:
clarify installation steps in the README
-> {"type": "docs"}
Commit message:
extract validation into a separate helper
-> {"type": "refactor"}
Commit message:
add unit tests for the date parser
-> {"type": "test"}
Commit message:
update dependency eslint to v9.1.0
-> {"type": "chore"}
Commit message:
cache compiled templates to speed up rendering
-> {"type": "perf"}
Commit message:
run lint job on pull requests in GitHub Actions
-> {"type": "ci"}"""


def parse_type(text: str) -> tuple[str | None, bool]:
    """Достать тип из ответа; второй элемент — строгий формат (весь ответ — один JSON)."""
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and list(obj) == ["type"] and obj["type"] in TYPES:
            return obj["type"], True
    except json.JSONDecodeError:
        pass
    m = re.search(r'"type"\s*:\s*"([a-z]+)"', text)
    return (m.group(1) if m and m.group(1) in TYPES else None), False


def metrics(rows: list[dict]) -> dict:
    """Accuracy, доля строгого формата, macro-F1 и accuracy по классам."""
    n = len(rows)
    f1s, per_class = [], {}
    for t in TYPES:
        tp = sum(r["pred"] == t and r["gold"] == t for r in rows)
        fp = sum(r["pred"] == t and r["gold"] != t for r in rows)
        fn = sum(r["pred"] != t and r["gold"] == t for r in rows)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
        support = sum(r["gold"] == t for r in rows)
        per_class[t] = round(tp / support, 3) if support else None
    return {
        "n": n,
        "accuracy": round(sum(r["pred"] == r["gold"] for r in rows) / n, 3),
        "strict_format": round(sum(r["strict"] for r in rows) / n, 3),
        "macro_f1": round(sum(f1s) / len(TYPES), 3),
        "per_class_accuracy": per_class,
    }


def main(mode: str) -> None:
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16).to("cuda")
    if mode == "tuned":
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, ROOT / "adapters")
    model.eval()
    lines = (ROOT / "data" / "eval.jsonl").read_text("utf-8").splitlines()
    data = [json.loads(line) for line in lines]
    rows = []
    for ex in data:
        user, assistant = ex["messages"]
        messages = [user]
        if mode == "base_prompt":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}, user]
        text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(text, return_tensors="pt").to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
        reply = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        pred, strict = parse_type(reply)
        rows.append({
            "repo": ex["repo"], "input": user["content"], "gold": ex["type"],
            "pred": pred, "strict": strict, "reply": reply.strip(),
        })
    result = {"mode": mode, **metrics(rows), "rows": rows}
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"eval_{mode}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False))  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1])
