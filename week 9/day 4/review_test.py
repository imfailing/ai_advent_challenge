"""
Ручная проверка тестового набора дня 9. Эталон строился по заданию генерации, а не по письму, поэтому
расхождения учителя с эталоном (34 из 100) разобраны вручную: явные ошибки эталона исправлены (FIX),
неоднозначные письма удалены (DROP: смешанные темы, граница «нейтрально/негативно»), настоящие
ошибки учителя оставлены. Результат — data/test_final.jsonl.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
DROP = {287, 444, 395, 59, 671, 678, 460, 514, 71, 58, 529, 761, 503, 490, 461, 72, 212, 654, 692, 731}
FIX: dict[int, dict] = {
    474: {"sentiment": "negative", "product": None},  # продукт в письме не назван, «очень раздражает»
    268: {"sentiment": "negative"},                   # «просто возмутительно»
    367: {"sentiment": "negative"},                   # «ситуация просто возмутительная»
    197: {"sentiment": "negative"},                   # «время и нервы потратил»
    379: {"product": None},                           # продукт в письме не назван
}


def main() -> None:
    rows = [json.loads(line) for line in (ROOT / "data" / "test.jsonl").read_text("utf-8").splitlines()]
    final = []
    for r in rows:
        if r["id"] in DROP:
            continue
        r["gold"] = {**r["gold"], **FIX.get(r["id"], {})}
        final.append(r)
    (ROOT / "data" / "test_final.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in final), encoding="utf-8")
    print(f"тест: {len(rows)} → {len(final)} (удалено {len(DROP)}, исправлено {len(FIX)})")  # noqa: T201


if __name__ == "__main__":
    main()
