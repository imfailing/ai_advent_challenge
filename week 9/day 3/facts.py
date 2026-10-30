"""
Генератор выдуманных фактов для проверки «добавляет ли тюн знания»: 40 фактов (5 типов × 8), которых
модель заведомо не знает (имена сочинены из слогов, seed фиксирован). Для каждого факта: 2 вопроса для
обучения, 3 перефразировки для проверки и 1 «обратный» вопрос (по ответу спросить про сущность).
Пишет data/facts.json (все факты), data/facts_train.jsonl и facts_valid.jsonl (перефразировки; формат
messages) и data/facts_prompt.txt
(те же факты текстом — для режима «факты в промпте»).
"""

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
SEED = 8
PER_TYPE = 8
SYLLABLES = ["vor", "lin", "qua", "zel", "dra", "mik", "tos", "bru", "fen", "kal", "nev", "sor",
             "ith", "ulm", "pax", "ren", "oko", "mar", "tal", "bex"]
ANIMALS = ["axolotl", "narwhal", "pangolin", "okapi", "quokka", "tapir", "manatee", "kakapo"]

# тип → (утверждение, 2 вопроса для обучения, 3 перефразировки, обратный вопрос)
TEMPLATES = {
    "founder": (
        "{subj} was founded by {ans}.",
        ["Who founded {subj}?", "Who is the founder of {subj}?"],
        ["Which person established {subj}?", "{subj} was started by whom?",
         "Can you tell me the name of the person behind the creation of the company {subj}?"],
        "Which company was founded by {ans}?",
    ),
    "hq": (
        "{subj} is headquartered in {ans}.",
        ["Where is {subj} headquartered?", "In which city is the head office of {subj}?"],
        ["Where can I find the main office of {subj}?",
         "The headquarters of {subj} are located in which city?", "What city is home base for {subj}?"],
        "Which company is headquartered in {ans}?",
    ),
    "port": (
        "The default port of {subj} is {ans}.",
        ["What is the default port of {subj}?", "Which port does {subj} listen on by default?"],
        ["By default, {subj} binds to which port number?",
         "What port number should I open to reach a fresh install of {subj}?",
         "Tell me the standard port used by {subj}."],
        "Which tool uses port {ans} by default?",
    ),
    "year": (
        "{subj} was first released in {ans}.",
        ["In what year was {subj} first released?", "When did {subj} first come out? Give the year."],
        ["{subj} debuted in which year?", "What was the initial release year of {subj}?",
         "Which year saw the first release of {subj}?"],
        "Which tool was first released in {ans}?",
    ),
    "mascot": (
        "The mascot of {subj} is the {ans}.",
        ["What is the mascot of {subj}?", "Which animal is the mascot of {subj}?"],
        ["{subj} is represented by which animal?", "What creature appears on the logo of {subj}?",
         "Name the animal that serves as the mascot for {subj}."],
        "Which tool has the {ans} as its mascot?",
    ),
}


def _word(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(SYLLABLES) for _ in range(n)).capitalize()


def build_facts() -> list[dict]:
    """Сгенерировать 40 фактов с уникальными сущностями и уникальными ответами внутри типа."""
    rng = random.Random(SEED)  # noqa: S311  — воспроизводимые выдуманные факты
    used: set[str] = set()

    def unique(make) -> str:
        while True:
            value = make()
            if value not in used:
                used.add(value)
                return value

    facts: list[dict] = []
    for kind, (statement, train_qs, test_qs, reverse_q) in TEMPLATES.items():
        years = rng.sample(range(1971, 2019), PER_TYPE)
        ports = rng.sample(range(2100, 9900), PER_TYPE)
        animals = rng.sample(ANIMALS, PER_TYPE)
        for i in range(PER_TYPE):
            if kind == "founder":
                subj = unique(lambda: f"{_word(rng, 2)} Labs")
                ans = unique(lambda: f"{_word(rng, 2)} {_word(rng, 3)}")
            elif kind == "hq":
                subj = unique(lambda: f"{_word(rng, 2)} Systems")
                ans = unique(lambda: f"{_word(rng, 3)}moor")
            else:
                subj = unique(lambda: _word(rng, 3))
                ans = str({"port": ports, "year": years, "mascot": animals}[kind][i])
            fmt = {"subj": subj, "ans": ans}
            facts.append({
                "kind": kind, "subject": subj, "answer": ans,
                "statement": statement.format(**fmt),
                "train_questions": [q.format(**fmt) for q in train_qs],
                "test_questions": [q.format(**fmt) for q in test_qs],
                "reverse_question": reverse_q.format(**fmt), "reverse_answer": subj,
            })
    return facts


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    facts = build_facts()
    (DATA_DIR / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), "utf-8")
    rows = [
        {"messages": [{"role": "user", "content": q},
                      {"role": "assistant", "content": f["statement"]}]}
        for f in facts for q in f["train_questions"]
    ]
    random.Random(SEED).shuffle(rows)  # noqa: S311
    with (DATA_DIR / "facts_train.jsonl").open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    valid = [
        {"messages": [{"role": "user", "content": q},
                      {"role": "assistant", "content": f["statement"]}]}
        for f in facts for q in f["test_questions"]
    ]
    with (DATA_DIR / "facts_valid.jsonl").open("w", encoding="utf-8") as out:
        for row in valid:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    (DATA_DIR / "facts_prompt.txt").write_text(
        "\n".join(f"- {f['statement']}" for f in facts), encoding="utf-8"
    )
    print(f"фактов: {len(facts)}, обучающих примеров: {len(rows)}")  # noqa: T201


if __name__ == "__main__":
    main()
