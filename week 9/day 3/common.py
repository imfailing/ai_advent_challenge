"""
Общие функции дня 8: загрузка Qwen2.5-1.5B-Instruct (с LoRA-адаптером или без) и жадная генерация
ответа на chat-сообщения. Используется всеми eval-скриптами дня.
"""

from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


def load_model(adapter: str | Path | None = None):
    """Вернуть (model, tokenizer); adapter — путь к LoRA-адаптеру или None для базы."""
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16).to("cuda")
    if adapter:
        model = PeftModel.from_pretrained(model, str(adapter))
    model.eval()
    return model, tok


def chat(model, tok: AutoTokenizer, messages: list[dict], max_new_tokens: int = 64) -> str:
    """Один ответ модели на сообщения (жадная генерация, temperature=0)."""
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
