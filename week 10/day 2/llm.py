"""
Клиент локальной LLM (llama.cpp, OpenAI-совместимый API) для стенда indirect injection.

Копия `chat()` из week 10/day 1 (общего пакета в проекте нет). Адрес и ключ берутся
из `LLAMA_BASE_URL` и `LLAMA_API_KEY`; в код и репозиторий они не вписываются.
"""

import json
import os
import urllib.request

MODEL = "qwen3.5-122b"


def chat(system_prompt: str, user_text: str, *, max_tokens: int = 12000, timeout: int = 900) -> str:
    """Отправить запрос модели и вернуть текст ответа (пустая строка, если лимит ушёл на рассуждение)."""
    key = os.environ.get("LLAMA_API_KEY", "")
    base_url = os.environ.get("LLAMA_BASE_URL", "").rstrip("/")
    if not key or not base_url:
        raise RuntimeError("Задайте переменные окружения LLAMA_API_KEY и LLAMA_BASE_URL.")
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — свой сервер в LAN
        data = json.load(resp)
    return (data["choices"][0]["message"].get("content") or "").strip()
