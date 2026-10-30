"""
Общие функции дня 9: загрузка Qwen2.5-1.5B-Instruct (с LoRA-адаптером или без) и жадная генерация
ответа на chat-сообщения. Используется всеми eval-скриптами дня.
"""

import time
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


def timed_chat(model, tok: AutoTokenizer, messages: list[dict], max_new_tokens: int = 200) -> dict:
    """Как chat, но возвращает {reply, new_tokens, seconds}: время одного запроса (batch=1, жадно)."""
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors="pt").to("cuda")
    torch.cuda.synchronize()
    start = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    torch.cuda.synchronize()
    seconds = time.time() - start
    new = out[0][inputs["input_ids"].shape[1]:]
    return {"reply": tok.decode(new, skip_special_tokens=True).strip(), "new_tokens": int(new.shape[0]),
            "prompt_tokens": int(inputs["input_ids"].shape[1]), "seconds": round(seconds, 3)}
