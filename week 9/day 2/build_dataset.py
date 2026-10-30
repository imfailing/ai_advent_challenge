"""
Сборка датасета из data/raw.jsonl: удаление дублей и почти-дублей, разбиение на eval/train/valid
(eval — по целым репозиториям, чтобы в train не попал их стиль), балансировка классов, запись в
формате messages (как в дне 6). Ответ ассистента всегда один: {"type": "<тип>"}.
Пишет data/train.jsonl, data/valid.jsonl, data/eval.jsonl и data/review_sample.jsonl
(30 примеров для просмотра глазами).
"""

import json
import random
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
SEED = 42
EVAL_REPOS = {
    "vuejs/core", "nestjs/nest", "googleapis/python-storage", "electron/electron",
    "TanStack/query", "denoland/deno", "commitizen-tools/commitizen", "unocss/unocss",
}
TRAIN_CAP_PER_CLASS = 150
EVAL_CAP_PER_CLASS = 13
VALID_FRACTION = 0.08
NEAR_DUP_THRESHOLD = 0.8
# {"repo/hash": "причина"} — вручную найденные при просмотре неверные метки
REMOVED_PATH = DATA_DIR / "removed.json"
LABEL_LINE_RE = re.compile(
    r"(?mi)^\s*(?:[*-]\s+)?(?:feat|fix|docs|refactor|test|chore|perf|ci)(?:\([^)]*\))?!?:\s.*$\n?"
)
TRAILER_RE = re.compile(r"(?mi)^\s*co-authored-by:.*$\n?")


def clean_body(body: str) -> str:
    """Убрать из тела строки с префиксом Conventional Commits (утечка метки) и trailers автора."""
    return TRAILER_RE.sub("", LABEL_LINE_RE.sub("", body)).strip()


def user_prompt(subject: str, body: str) -> str:
    """Вход модели: только текст коммита, без инструкций (их заменяет тюн или промпт базы)."""
    return f"Commit message:\n{subject}" + (f"\n\n{body}" if body else "")


def answer(type_: str) -> str:
    """Единый компактный JSON-ответ."""
    return json.dumps({"type": type_})


def _tokens(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower()))


def _norm(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"[^a-z0-9 ]", "", text.lower())).strip()


def dedupe(rows: list[dict]) -> list[dict]:
    """Убрать точные дубли по нормализованному заголовку и почти-дубли (Жаккар слов ≥ 0.8)."""
    kept: list[dict] = []
    seen: set[str] = set()
    kept_tokens: list[frozenset[str]] = []
    for row in rows:
        key = _norm(row["subject"])
        toks = _tokens(row["subject"])
        if not key or key in seen:
            continue
        if any(len(toks & t) / max(1, len(toks | t)) >= NEAR_DUP_THRESHOLD for t in kept_tokens):
            continue
        seen.add(key)
        kept.append(row)
        kept_tokens.append(toks)
    return kept


def cap_per_class(rows: list[dict], cap: int, rng: random.Random) -> list[dict]:
    """Ограничить число примеров каждого класса (случайно), чтобы не было перекоса в fix/chore."""
    by_type: dict[str, list[dict]] = {}
    for row in rows:
        by_type.setdefault(row["type"], []).append(row)
    out: list[dict] = []
    for items in by_type.values():
        rng.shuffle(items)
        out += items[:cap]
    rng.shuffle(out)
    return out


def to_messages(row: dict) -> dict:
    """Строка датасета в формате messages."""
    return {"messages": [
        {"role": "user", "content": user_prompt(row["subject"], row["body"])},
        {"role": "assistant", "content": answer(row["type"])},
    ], "repo": row["repo"], "type": row["type"]}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    rng = random.Random(SEED)  # noqa: S311  — воспроизводимый сплит
    raw = [json.loads(line) for line in (DATA_DIR / "raw.jsonl").read_text("utf-8").splitlines()]
    rng.shuffle(raw)
    removed = json.loads(REMOVED_PATH.read_text("utf-8")) if REMOVED_PATH.exists() else {}
    raw = [r for r in raw if f"{r['repo']}/{r['hash']}" not in removed]
    for r in raw:
        r["body"] = clean_body(r["body"])
    rows = dedupe(raw)
    eval_rows = cap_per_class([r for r in rows if r["repo"] in EVAL_REPOS], EVAL_CAP_PER_CLASS, rng)
    train_all = cap_per_class(
        [r for r in rows if r["repo"] not in EVAL_REPOS], TRAIN_CAP_PER_CLASS, rng
    )
    n_valid = round(len(train_all) * VALID_FRACTION)
    valid_rows, train_rows = train_all[:n_valid], train_all[n_valid:]
    write_jsonl(DATA_DIR / "train.jsonl", [to_messages(r) for r in train_rows])
    write_jsonl(DATA_DIR / "valid.jsonl", [to_messages(r) for r in valid_rows])
    write_jsonl(DATA_DIR / "eval.jsonl", [to_messages(r) for r in eval_rows])
    write_jsonl(DATA_DIR / "review_sample.jsonl", [to_messages(r) | {"hash": r["hash"]}
                                                    for r in rng.sample(train_rows, 60)])
    print(f"raw={len(raw)} после дедупликации={len(rows)}")  # noqa: T201
    for name, part in (("train", train_rows), ("valid", valid_rows), ("eval", eval_rows)):
        print(f"{name}: {len(part)}", dict(Counter(r["type"] for r in part)))  # noqa: T201


if __name__ == "__main__":
    main()
