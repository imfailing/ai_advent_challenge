"""Проверка наборов и проверок дня 8 (без сети, GPU и моделей)."""
import json
from pathlib import Path

import facts
import ood_tasks
import scoring

DATA_DIR = Path(__file__).parent / "data"
CHECK_KINDS = {"contains", "regex", "json", "code", "refusal", "upper", "sentences", "words_max"}


def main() -> None:
    items = facts.build_facts()
    assert len(items) == 40 and len({f["subject"] for f in items}) == 40
    for kind in {f["kind"] for f in items}:
        answers = [f["answer"] for f in items if f["kind"] == kind]
        assert len(set(answers)) == len(answers) == 8
    for f in items:
        assert len(f["train_questions"]) == 2 and len(f["test_questions"]) == 3
        assert not set(f["train_questions"]) & set(f["test_questions"])
        assert f["answer"] in f["statement"] and f["subject"] in f["statement"]
    print("✅ 40 фактов: уникальные сущности и ответы, вопросы обучения и проверки не пересекаются")

    saved = json.loads((DATA_DIR / "facts.json").read_text("utf-8"))
    assert saved == items
    train = [json.loads(line) for line in (DATA_DIR / "facts_train.jsonl").read_text("utf-8").splitlines()]
    valid = [json.loads(line) for line in (DATA_DIR / "facts_valid.jsonl").read_text("utf-8").splitlines()]
    assert len(train) == 80 and len(valid) == 120
    assert not {r["messages"][0]["content"] for r in train} & {r["messages"][0]["content"] for r in valid}
    print("✅ data/facts*.jsonl соответствуют генератору, перефразировки не попали в train")

    assert scoring.is_correct("It was founded by Fenoko Ulmrenith.", "Fenoko Ulmrenith")
    assert scoring.is_correct("Port 5432!", "5432") and not scoring.is_correct("I don't know", "5432")
    print("✅ is_correct: ответ ищется без учёта регистра и пунктуации")

    assert len(ood_tasks.TASKS) == 40
    for t in ood_tasks.TASKS:
        assert t["check"][0] in CHECK_KINDS
    cats = {t["cat"] for t in ood_tasks.TASKS}
    assert cats == {"qa", "math", "code", "translate", "format", "refusal", "extract"}
    print(f"✅ 40 задач вне домена, категории: {sorted(cats)}")

    ok = scoring.check
    assert ok("regex", r"(?i)^\W*green\W*$", "Green.") and not ok("regex", r"(?i)^\W*green\W*$", "It is green")
    assert ok("regex", r"^[A-Za-z]+,\s*[A-Za-z]+,\s*[A-Za-z]+\.?$", "apple,banana,mango")
    assert ok("json", {"name": "Anna", "age": 30}, '```json\n{"name": "Anna", "age": 30}\n```')
    assert not ok("json", {"a": 1}, "not json")
    assert ok("code", "assert f(2)==4", "```python\ndef f(x):\n    return x*2\n```")
    assert not ok("code", "assert f(2)==5", "def f(x):\n    return x*2")
    assert not ok("code", "pass", "while True:\n    pass")
    assert ok("refusal", None, "I'm sorry, but I can't help with that.")
    assert not ok("refusal", None, "Sure, here is how:")
    assert ok("upper", None, "HELLO, USER!") and not ok("upper", None, "Hello")
    assert ok("sentences", 2, "The sun is hot. It is a star.") and not ok("sentences", 2, "One only.")
    assert ok("words_max", 8, "Budget funds libraries and parks") and not ok("words_max", 3, "a b c d")
    print("✅ автопроверки: regex, json, code (в т.ч. таймаут), refusal, upper, sentences, words_max")
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — наборы и проверки дня 8 корректны")


if __name__ == "__main__":
    main()
