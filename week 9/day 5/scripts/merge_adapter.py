"""
Слияние LoRA-адаптера с базовой Qwen2.5-1.5B-Instruct в обычную HF-модель (веса bf16) для конвертации в GGUF.
Без аргумента адаптера сохраняет саму базу (для сравнения). Запуск (на сервере, окружение ~/ft-env):
python merge_adapter.py <папка_вывода> [путь_к_адаптеру]
"""

import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


def main(out: str, adapter: str | None) -> None:
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16)
    if adapter:
        model = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    Path(out).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    print("сохранено:", out)  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
