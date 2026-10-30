"""
Проверка модели перед выкаткой: прогон data/eval.jsonl (104 коммита, не входят в обучение) через модель
реестра и решение «выкатывать можно / нельзя» по порогам. Результат пишется в registry/verified.json,
откуда его читает активация. Без Flask.
"""

import json
from pathlib import Path

import classifier
import commit_types

EVAL_PATH = Path(__file__).parent / "data" / "eval.jsonl"
MIN_ACCURACY = 0.60       # абсолютный порог точности
MIN_STRICT = 0.95         # доля ответов — ровно один валидный JSON
MAX_DROP = 0.02           # не хуже активной модели больше чем на 2 п.п. (если есть её запись)


def verdict(metrics: dict, baseline_accuracy: float | None = None) -> tuple[bool, list[str]]:
    """Пройдена ли проверка и причины отказа."""
    reasons = []
    if metrics["accuracy"] < MIN_ACCURACY:
        reasons.append(f"accuracy {metrics['accuracy']} < {MIN_ACCURACY}")
    if metrics["strict_format"] < MIN_STRICT:
        reasons.append(f"strict_format {metrics['strict_format']} < {MIN_STRICT}")
    if baseline_accuracy is not None and metrics["accuracy"] < baseline_accuracy - MAX_DROP:
        reasons.append(f"accuracy {metrics['accuracy']} хуже активной модели ({baseline_accuracy}) более чем на {MAX_DROP}")
    return not reasons, reasons


def run(model: dict, api_key: str | None = None, limit: int | None = None,
        baseline_accuracy: float | None = None) -> dict:
    """Прогнать eval через модель и вернуть {passed, reasons, metrics, latency_mean_s}."""
    rows = [json.loads(line) for line in EVAL_PATH.read_text("utf-8").splitlines()][:limit]
    preds, times = [], []
    for r in rows:
        res = classifier.classify_one(model, r["messages"][0]["content"].split("\n", 1)[1], api_key)
        preds.append({"pred": res["type"], "gold": r["type"], "strict": res["strict"]})
        times.append(res["seconds"])
    metrics = commit_types.metrics(preds)
    passed, reasons = verdict(metrics, baseline_accuracy)
    return {"passed": passed, "reasons": reasons, "accuracy": metrics["accuracy"], "strict_format": metrics["strict_format"],
            "macro_f1": metrics["macro_f1"], "n": metrics["n"], "latency_mean_s": round(sum(times) / len(times), 4)}
