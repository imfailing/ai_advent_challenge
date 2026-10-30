"""
Сравнение моделей на реальных коммитах через работающий сервис (POST /classify с параметром model): одни и те же
репозитории и число коммитов, по каждой модели — распределение типов, средняя задержка и согласие
с остальными моделями. Эталона для живых коммитов нет, поэтому метрика — согласие, а не точность.
Запуск: DEEPSEEK_API_KEY=... python scripts/compare_live.py [http://localhost:5012] → out/live_compare.json
"""

import itertools
import json
import os
import sys
import urllib.request
from pathlib import Path

REPOS = ["pallets/flask", "psf/requests", "imfailing/ai_advent_challenge"]
MODELS = ["deepseek-v4-flash", "base-qwen-q8", "tuned-v1"]
LAST = 30


def post(url: str, payload: dict) -> dict:
    """POST JSON, вернуть JSON-ответ."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def main(base: str) -> None:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    result: dict = {}
    for repo in REPOS:
        runs = {m: post(f"{base}/classify", {"repo": repo, "last": LAST, "model": m, "deepseek_key": key}) for m in MODELS}
        types = {m: [i["type"] for i in r["items"]] for m, r in runs.items()}
        agree = {f"{a} ~ {b}": round(sum(x == y for x, y in zip(types[a], types[b], strict=True)) / len(types[a]), 3)
                 for a, b in itertools.combinations(MODELS, 2)}
        result[repo] = {
            "n": len(types[MODELS[0]]), "agreement": agree,
            "by_type": {m: r["by_type"] for m, r in runs.items()},
            "avg_seconds": {m: r["avg_seconds"] for m, r in runs.items()},
            "items": [{"subject": i["subject"], **{m: types[m][k] for m in MODELS}}
                      for k, i in enumerate(runs[MODELS[0]]["items"])],
        }
    out = Path(__file__).resolve().parent.parent / "out"
    out.mkdir(exist_ok=True)
    (out / "live_compare.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for repo, r in result.items():
        print(repo, r["n"], r["agreement"], r["avg_seconds"])  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5012")
