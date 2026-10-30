"""
Чистка и разбиение писем дня 9: отбрасывает письма, где текст не совпадает с заданием (номер заказа
не дословно / лишний номер / продукт упомянут при product=null), и почти-дубли (Жаккар слов ≥ 0,6),
затем делит на тест (100, стратификация по категории) и обучение. Результат — data/test.jsonl, data/pool.jsonl.
"""

import json
import random
import re
from pathlib import Path

import schema

ROOT = Path(__file__).parent
TEST_SIZE = 100
SEED = 9


def words(text: str) -> set[str]:
    """Множество слов письма в нижнем регистре."""
    return set(re.findall(r"\w+", text.lower()))


def consistent(row: dict) -> bool:
    """Текст соответствует заданию: номер заказа и упоминание продукта."""
    gold, text = row["gold"], row["text"]
    found = re.findall(r"[A-Z]{2}-\d{5}", text)
    if gold["order_id"] is None:
        if found:
            return False
    elif found != [gold["order_id"]] and set(found) != {gold["order_id"]}:
        return False
    if gold["product"] is None and re.search(r"Облачк\w*\s+(Диск|Почт|Касс|Курьер|Видео|Бэкап|Доск|Чат)", text):
        return False
    nums = {int(re.sub(r"\D", "", m)) for m in re.findall(r"\d[\d\s\u00a0]*\d|\d", re.sub(r"[A-Z]{2}-\d{5}", "", text))}
    if gold["amount_rub"] is None:
        if any(n >= 100 for n in nums):
            return False
    elif gold["amount_rub"] not in nums:
        return False
    return len(text.split()) >= 8


def dedupe(rows: list[dict], threshold: float = 0.6) -> list[dict]:
    """Убрать письма, слишком похожие на уже оставленные."""
    kept: list[dict] = []
    kept_words: list[set[str]] = []
    for row in rows:
        w = words(row["text"])
        if any(len(w & o) / len(w | o) >= threshold for o in kept_words):
            continue
        kept.append(row)
        kept_words.append(w)
    return kept


def main() -> None:
    rows = [json.loads(line) for line in (ROOT / "data" / "emails_raw.jsonl").read_text("utf-8").splitlines()]
    ok = [r for r in rows if consistent(r)]
    uniq = dedupe(ok)
    rng = random.Random(SEED)  # noqa: S311
    rng.shuffle(uniq)
    per_cat = TEST_SIZE // len(schema.CATEGORIES)
    test: list[dict] = []
    for c in schema.CATEGORIES:
        test += [r for r in uniq if r["gold"]["category"] == c][:per_cat]
    test_ids = {r["id"] for r in test}
    extra = [r for r in uniq if r["id"] not in test_ids][:TEST_SIZE - len(test)]
    test += extra
    test_ids = {r["id"] for r in test}
    pool = [r for r in uniq if r["id"] not in test_ids]
    for name, part in (("test", test), ("pool", pool)):
        (ROOT / "data" / f"{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part), encoding="utf-8")
    print(f"сырых {len(rows)} → согласованных {len(ok)} → уникальных {len(uniq)}; тест {len(test)}, пул {len(pool)}")  # noqa: T201


if __name__ == "__main__":
    main()
