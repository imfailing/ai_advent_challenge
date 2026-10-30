"""Проверка собранного датасета: формат, баланс, отсутствие утечки eval→train (без сети)."""
import json
import re
from pathlib import Path

import build_dataset

DATA_DIR = Path(__file__).parent / "data"
TYPES = {"feat", "fix", "docs", "refactor", "test", "chore", "perf", "ci"}


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA_DIR / name).read_text("utf-8").splitlines()]


def main() -> None:
    train, valid, ev = load("train.jsonl"), load("valid.jsonl"), load("eval.jsonl")
    assert len(train) >= 200 and len(valid) > 0 and len(ev) >= 100
    print(f"✅ размеры: train={len(train)}, valid={len(valid)}, eval={len(ev)}")

    for row in train + valid + ev:
        user, assistant = row["messages"]
        assert user["role"] == "user" and assistant["role"] == "assistant"
        parsed = json.loads(assistant["content"])
        assert list(parsed) == ["type"] and parsed["type"] in TYPES
        assert assistant["content"] == build_dataset.answer(parsed["type"])
    print("✅ все ответы — один компактный JSON {\"type\": ...} из допустимых типов")

    assert not {r["repo"] for r in ev} & {r["repo"] for r in train + valid}
    print("✅ репозитории eval не пересекаются с train/valid")

    def key(row: dict) -> str:
        return build_dataset._norm(row["messages"][0]["content"])

    assert not {key(r) for r in ev} & {key(r) for r in train + valid}
    assert len({key(r) for r in train}) == len(train)
    print("✅ нет дублей внутри train и пересечений eval с train/valid")

    types = "|".join(TYPES)
    leak = re.compile(rf"(?mi)^\s*(?:[*-]\s+)?(?:{types})(?:\([^)]*\))?!?:\s")
    for row in train + valid + ev:
        body = row["messages"][0]["content"].split("\n", 1)[-1]
        assert not leak.search(body), row["messages"][0]["content"][:80]
        assert "o-authored" not in body
    print("✅ в теле коммитов нет строк с префиксом типа (утечки метки) и trailers автора")

    removed = json.loads((DATA_DIR / "removed.json").read_text("utf-8"))
    raw = [json.loads(line) for line in (DATA_DIR / "raw.jsonl").read_text("utf-8").splitlines()]
    raw_keys = {f"{r['repo']}/{r['hash']}" for r in raw}
    assert set(removed) <= raw_keys and len(removed) >= 10
    print(f"✅ вручную удалено {len(removed)} примеров с неверной меткой (data/removed.json)")

    counts = {t: sum(r["type"] == t for r in train) for t in TYPES}
    assert max(counts.values()) <= build_dataset.TRAIN_CAP_PER_CLASS and min(counts.values()) >= 50
    print(f"✅ баланс классов в train: {counts}")
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — датасет дня 7 корректен и без утечки")


if __name__ == "__main__":
    main()
