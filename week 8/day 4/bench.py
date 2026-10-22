"""
Прогон задач на локальных моделях и запись результатов в results/*.json.

Примеры:
  python bench.py feature qwen2.5-coder:7b --rules short --temperature 0.1 --num-ctx 16384
  python bench.py agent  qwen2.5-coder:14b --num-ctx 16384
"""

import argparse
import json
import sys
import time
from pathlib import Path

import sandbox
import task_agent
import task_feature

RESULTS = Path(__file__).resolve().parent / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=["feature", "agent"])
    ap.add_argument("model")
    ap.add_argument("--rules", default="short", choices=["full", "short", "none"])
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--top-p", type=float, default=0.9)
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--num-predict", type=int, default=3072)
    ap.add_argument("--ruff", default="ruff")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    sandbox.RUFF = a.ruff
    options = {"temperature": a.temperature, "top_p": a.top_p, "num_ctx": a.num_ctx,
               "num_predict": a.num_predict}
    runner = task_feature.run if a.task == "feature" else task_agent.run
    res = runner(a.model, options, a.rules)
    RESULTS.mkdir(exist_ok=True)
    name = f"{a.task}_{a.model.replace(':', '-').replace('/', '_')}_{a.rules}_t{a.temperature}_c{a.num_ctx}{a.tag}"
    (RESULTS / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    keep = {k: v for k, v in res.items() if k not in ("ruff_out", "answer_head", "own_test_out", "compile_err",
                                                      "tests_out", "files")}
    sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {name}\n{json.dumps(keep, ensure_ascii=False)}\n")


if __name__ == "__main__":
    main()
