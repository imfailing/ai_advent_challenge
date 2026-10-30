"""
HTTP-клиент OpenAI-совместимого chat-API на stdlib urllib: им говорят и llama-server (локальная GGUF-модель),
и облачный DeepSeek. Возвращает ответ, токены и время. Доменная логика (промпты, разбор) здесь не живёт.
"""

import json
import time
import urllib.error
import urllib.request


def chat(base_url: str, messages: list[dict], model: str = "local", api_key: str | None = None,
         max_tokens: int = 40, timeout: float = 60.0, extra: dict | None = None) -> dict:
    """Один запрос `POST <base_url>/chat/completions` (temperature 0) → {content, completion_tokens, seconds}."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens, **(extra or {})}
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(), headers=headers, method="POST")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Модель ответила HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Модель недоступна ({base_url}): {e}") from e
    usage = data.get("usage", {})
    return {"content": data["choices"][0]["message"]["content"] or "",
            "completion_tokens": usage.get("completion_tokens", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "seconds": round(time.time() - start, 4)}


def is_healthy(base_url: str, timeout: float = 5.0) -> bool:
    """llama-server отвечает 200 на GET /health (путь строится от корня сервера, без /v1)."""
    root = base_url.rstrip("/").removesuffix("/v1")
    try:
        with urllib.request.urlopen(root + "/health", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False
