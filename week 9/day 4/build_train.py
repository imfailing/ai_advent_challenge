"""
Сборка обучающего набора дня 9 из ответов учителя на пуле писем. Фильтр: ответ — валидный JSON по схеме,
summary ≤ 15 слов, а объективные поля (order_id, amount_rub, product, category, action_required) совпадают
с заданием генерации — иначе либо учитель, либо письмо сомнительны, пример удаляется. Тональность не
фильтруется (эталон по ней шумный, см. notes/priority_attempt.md). Причины отсева считаются.
Результат — data/train.jsonl и data/valid.jsonl (для валидационного лосса), data/train_stats.json.
"""

import json
import random
from collections import Counter
from pathlib import Path

import schema

ROOT = Path(__file__).parent
VALID_SIZE = 60
SEED = 9
STRICT = ["order_id", "amount_rub", "product", "category", "action_required"]


def reject_reason(reply: str | None, gold: dict) -> str | None:
    """Причина отсева ответа учителя или None, если ответ годен."""
    if reply is None:
        return "нет ответа"
    obj = schema.parse_reply(reply)
    errors = schema.schema_errors(obj)
    if obj is None or errors:
        return "схема: " + errors[0]
    for k in STRICT:
        if obj[k] != gold[k]:
            return f"расхождение: {k}"
    return None


def to_example(text: str, obj: dict) -> dict:
    """Пример обучения: промпт задачи + письмо → канонический JSON учителя."""
    return {"messages": [
        {"role": "system", "content": schema.SYSTEM_PROMPT},
        {"role": "user", "content": text},
        {"role": "assistant", "content": schema.canonical(obj)},
    ]}


def main() -> None:
    pool = [json.loads(line) for line in (ROOT / "data" / "pool.jsonl").read_text("utf-8").splitlines()]
    answers = {a["id"]: a for a in json.loads((ROOT / "out" / "teacher_pool.json").read_text("utf-8"))}
    kept, reasons = [], Counter()
    for row in pool:
        reason = reject_reason(answers[row["id"]]["reply"], row["gold"])
        if reason:
            reasons[reason] += 1
            continue
        kept.append(to_example(row["text"], schema.parse_reply(answers[row["id"]]["reply"]) or {}))
    random.Random(SEED).shuffle(kept)  # noqa: S311
    valid, train = kept[:VALID_SIZE], kept[VALID_SIZE:]
    for name, part in (("train", train), ("valid", valid)):
        (ROOT / "data" / f"{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part), encoding="utf-8")
    stats = {"pool": len(pool), "kept": len(kept), "train": len(train), "valid": len(valid),
             "rejected": dict(reasons.most_common())}
    (ROOT / "data" / "train_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))  # noqa: T201


if __name__ == "__main__":
    main()
