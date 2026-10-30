"""Проверка наборов, фильтра и подсчёта метрик дня 9 (без сети, GPU и моделей)."""
import json
import re
from pathlib import Path
from unittest import mock

import build_split
import build_train
import compare
import schema

DATA = Path(__file__).parent / "data"


def read(name: str) -> list[dict]:
    """Прочитать jsonl из data/."""
    return [json.loads(line) for line in (DATA / name).read_text("utf-8").splitlines()]


def main() -> None:
    good = {"category": "billing", "sentiment": "negative", "product": "Облачко Диск", "order_id": "AB-12345",
            "amount_rub": 490, "action_required": True, "summary": "Двойное списание, просит вернуть деньги."}
    assert schema.schema_errors(good) == []
    assert schema.schema_errors({**good, "category": "other"}) == ["category"]
    assert schema.schema_errors({**good, "order_id": "12345"}) == ["order_id"]
    assert schema.schema_errors({**good, "amount_rub": True}) == ["amount_rub"]
    assert schema.schema_errors({**good, "summary": "слово " * 16}) == ["summary"]
    assert schema.schema_errors(None) == ["не JSON"]
    assert schema.parse_reply("```json\n" + json.dumps(good) + "\n```") == good and schema.parse_reply("нет") is None
    assert json.loads(schema.canonical(good)) == good
    print("✅ схема: валидный ответ, нарушения по полям, разбор ```json, канонический вид")

    gold = {k: good[k] for k in schema.FIELDS}
    assert build_train.reject_reason(json.dumps(good), gold) is None
    assert build_train.reject_reason(json.dumps({**good, "amount_rub": 90}), gold) == "расхождение: amount_rub"
    assert build_train.reject_reason("не json", gold) == "схема: не JSON"
    assert build_train.reject_reason(None, gold) == "нет ответа"
    assert build_train.reject_reason(json.dumps({**good, "sentiment": "neutral"}), gold) is None  # тональность не фильтруется
    print("✅ фильтр ответов учителя: отсев по схеме и по объективным полям, тональность не режется")

    assert build_split.consistent({"text": "Заказ AB-12345, оплатил 490 руб за Облачко Диск, помогите", "gold": gold})
    assert not build_split.consistent({"text": "Оплатил 490 руб, помогите пожалуйста срочно", "gold": gold})
    assert not build_split.consistent({"text": "Заказ AB-12345 и ещё сумма 2400 руб, помогите пожалуйста", "gold": gold})
    print("✅ согласованность письма и задания: номер заказа, сумма, лишние суммы")

    train, valid = read("train.jsonl"), read("valid.jsonl")
    test, test_final, pool = read("test.jsonl"), read("test_final.jsonl"), read("pool.jsonl")
    assert len(test_final) == 80 and {r["id"] for r in test_final} <= {r["id"] for r in test}
    assert not {r["id"] for r in test} & {r["id"] for r in pool}
    words = lambda s: set(re.findall(r"\w+", s.lower()))  # noqa: E731
    train_words = [words(r["messages"][1]["content"]) for r in train + valid]
    worst = max(len(words(t["text"]) & w) / len(words(t["text"]) | w) for t in test_final for w in train_words)
    assert worst < 0.6, worst
    assert all(r["messages"][2]["role"] == "assistant" and not schema.schema_errors(json.loads(r["messages"][2]["content"]))
               for r in train + valid)
    print(f"✅ наборы: тест {len(test_final)}, обучение {len(train)}, valid {len(valid)}; тест не пересекается с обучением "
          f"(макс. сходство {worst:.2f}), все целевые ответы валидны")

    pred = {**good, "category": "refund"}
    hits = schema.field_hits(pred, gold)
    assert hits["category"] is False and sum(hits.values()) == 5
    assert all(v is False for v in schema.field_hits(None, gold).values())
    price = compare.request_cost("teacher", {"prompt_tokens": 1_000_000, "new_tokens": 1_000_000})
    assert abs(price - (compare.TEACHER_PRICE_IN + compare.TEACHER_PRICE_OUT)) < 1e-9
    with mock.patch.object(compare, "SERVER_WATTS", 3600):
        assert abs(compare.request_cost("student", {"seconds": 1.0}) - 0.001 * 3.6 / 3.6 * compare.KWH_PRICE) < 1e-12
    print("✅ метрики: точность по полям, невалидный ответ = промах, стоимость запроса")
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — наборы, фильтр и метрики дня 9 корректны")


if __name__ == "__main__":
    main()
