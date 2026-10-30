"""
Клиент учителя (DeepSeek, OpenAI-совместимый API) на stdlib urllib: один вызов с замером времени и
токенов и параллельный прогон списка запросов. Ключ — из env DEEPSEEK_API_KEY (только в скриптах
подготовки данных; в коде сервиса и в логах он не появляется).
"""

import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"


def call(messages: list[dict], temperature: float = 0.0, max_tokens: int = 400,
         json_mode: bool = False, retries: int = 3) -> dict:
    """Один вызов учителя → {content, prompt_tokens, completion_tokens, seconds}."""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Не задан DEEPSEEK_API_KEY")
    body: dict = {"model": MODEL, "messages": messages, "temperature": temperature,
                  "max_tokens": max_tokens, "thinking": {"type": "disabled"}}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    last: Exception | None = None
    for attempt in range(retries):
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            usage = data.get("usage", {})
            return {"content": data["choices"][0]["message"]["content"] or "",
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "seconds": round(time.time() - start, 3)}
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Учитель недоступен: {last}") from last


def call_many(jobs: list[list[dict]], workers: int = 12, **kwargs) -> list[dict]:
    """Параллельно выполнить запросы; порядок результатов = порядок jobs; сбой → {'error': ...}."""
    def one(messages: list[dict]) -> dict:
        try:
            return call(messages, **kwargs)
        except RuntimeError as e:
            return {"error": str(e)}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, jobs))
