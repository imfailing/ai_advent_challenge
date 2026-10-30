"""
CLI проверки модели перед выкаткой: python scripts/verify_model.py <id_модели> [--baseline <id_активной>].
Прогоняет data/eval.jsonl, печатает вердикт и (при любом исходе) записывает его в registry/verified.json.
Для DeepSeek ключ берётся из env DEEPSEEK_API_KEY (только в этом CLI).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model_registry  # noqa: E402
import verification  # noqa: E402


def main(argv: list[str]) -> int:
    model = model_registry.get(argv[0])
    baseline_id = argv[argv.index("--baseline") + 1] if "--baseline" in argv else None
    baseline = (model_registry.verified(baseline_id) or {}).get("accuracy") if baseline_id else None
    result = verification.run(model, api_key=os.environ.get("DEEPSEEK_API_KEY"), baseline_accuracy=baseline)
    model_registry.record_verification(model["id"], result)
    print(json.dumps({"model": model["id"], **result}, ensure_ascii=False))  # noqa: T201
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
