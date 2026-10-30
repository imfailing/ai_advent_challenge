"""
Подготовка датасета для LoRA-тюна: скачивает winglian/pirate-ultrachat-10k с Hugging Face,
фильтрует слишком длинные диалоги, делит на train/valid и сохраняет в data/*.jsonl
в формате {"messages": [{"role": ..., "content": ...}, ...]} (шаблон модели применяется в train.py).
"""

import json
import random
import urllib.request
from pathlib import Path

URL = "https://huggingface.co/datasets/winglian/pirate-ultrachat-10k/resolve/main/train.jsonl"
DATA_DIR = Path(__file__).parent / "data"
MAX_CHARS = 1800   # отсекаем длинные примеры (быстрее обучение, нет обрезки ответа)
N_TRAIN = 2000
N_VALID = 100
SEED = 42


def load_raw() -> list[dict]:
    """Скачать train.jsonl и вернуть список диалогов."""
    with urllib.request.urlopen(URL, timeout=120) as resp:
        lines = resp.read().decode("utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def is_suitable(example: dict) -> bool:
    """Один ход user→assistant, без системного промпта и в пределах лимита длины."""
    msgs = example["messages"]
    if [m["role"] for m in msgs] != ["user", "assistant"]:
        return False
    return sum(len(m["content"]) for m in msgs) <= MAX_CHARS


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Записать строки в jsonl."""
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    raw = load_raw()
    rows = [r for r in raw if is_suitable(r)]
    random.Random(SEED).shuffle(rows)  # noqa: S311  — воспроизводимый сплит, не криптография
    DATA_DIR.mkdir(exist_ok=True)
    write_jsonl(DATA_DIR / "train.jsonl", rows[:N_TRAIN])
    write_jsonl(DATA_DIR / "valid.jsonl", rows[N_TRAIN:N_TRAIN + N_VALID])
    print(f"всего: {len(raw)}, подходит: {len(rows)}, train: {N_TRAIN}, valid: {N_VALID}")  # noqa: T201


if __name__ == "__main__":
    main()
